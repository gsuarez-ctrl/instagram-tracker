import os
import json
import time
import random
import logging
import re
import requests
from playwright.sync_api import sync_playwright
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
        )
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def verify_login(self):
        success_indicators = [
            lambda: not bool(self.page.query_selector('input[name="username"]')),
            lambda: bool(self.page.query_selector('[aria-label="Search"]')),
            lambda: bool(self.page.query_selector('[aria-label="Home"]')),
            lambda: bool(self.page.query_selector('svg[aria-label="Home"]')),
            lambda: bool(self.page.query_selector('a[href="/explore/"]')),
            lambda: 'login' not in self.page.url
        ]
        return any(indicator() for indicator in success_indicators)

    def login(self):
        try:
            logger.info("Navigating to Instagram login page...")
            self.page.goto('https://www.instagram.com/accounts/login/')
            time.sleep(4)

            logger.info("Entering login credentials...")
            username_field = self.page.wait_for_selector('input[name="username"]', timeout=15000)
            if not username_field:
                raise Exception("Username field not found")
            
            username_field.fill(self.username)
            time.sleep(2)

            password_field = self.page.wait_for_selector('input[name="password"]')
            if not password_field:
                raise Exception("Password field not found")
            
            password_field.fill(self.password)
            time.sleep(2)

            submit_button = self.page.wait_for_selector('button[type="submit"]')
            if not submit_button:
                raise Exception("Submit button not found")
            
            submit_button.click()
            time.sleep(5)

            max_attempts = 3
            login_verified = False
            
            for attempt in range(max_attempts):
                logger.info(f"Login verification attempt {attempt + 1}/{max_attempts}")
                if self.verify_login():
                    login_verified = True
                    break
                time.sleep(5)

            if not login_verified:
                self.page.goto('https://www.instagram.com/')
                time.sleep(3)
                
                if not self.verify_login():
                    self.page.screenshot(path='login_failed.png')
                    raise Exception("Could not verify successful login")

            logger.info("Successfully logged in to Instagram")
            return True

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            try:
                self.page.screenshot(path='login_error.png')
            except:
                pass
            raise

    def get_follower_count(self, username):
        """Get follower count using multiple extraction methods"""
        try:
            logger.info(f"Getting follower count for {username}...")
            self.page.goto(f'https://www.instagram.com/{username}/')
            time.sleep(5)

            page_source = self.page.content()
            with open(f'debug_{username}_source.html', 'w', encoding='utf-8') as f:
                f.write(page_source)

            shared_data = self.page.evaluate('''() => {
                try {
                    return window._sharedData;
                } catch (e) {
                    return null;
                }
            }''')

            if shared_data and 'entry_data' in shared_data:
                try:
                    user_info = shared_data['entry_data']['ProfilePage'][0]['graphql']['user']
                    count = user_info['edge_followed_by']['count']
                    logger.info(f"Found follower count from shared data: {count}")
                    return count
                except KeyError:
                    logger.warning("Shared data format has changed, unable to access follower count.")
                    raise

            cookies = '; '.join([f"{c['name']}={c['value']}" for c in self.page.context.cookies()])
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/json',
                'Cookie': cookies
            }

            response = requests.get(
                f'https://i.instagram.com/api/v1/users/web_profile_info/?username={username}',
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'data' in data and 'user' in data['data']:
                        count = data['data']['user']['edge_followed_by']['count']
                        logger.info(f"Found follower count from API: {count}")
                        return count
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error for {username}: {response.text}")
                    raise

            logger.error(f"Could not find follower count for {username}")
            self.page.screenshot(path=f'debug_{username}.png')
            return None

        except Exception as e:
            logger.error(f"Error getting followers for {username}: {str(e)}")
            self.page.screenshot(path=f'error_{username}.png')
            return None

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number"""
        try:
            count_text = str(count_text).strip().replace(',', '').lower()
            
            multiplier = 1
            if 'k' in count_text:
                multiplier = 1000
                count_text = count_text.replace('k', '')
            elif 'm' in count_text:
                multiplier = 1000000
                count_text = count_text.replace('m', '')

            number = float(count_text) * multiplier
            result = int(round(number))
            return result if result > 0 else None
        except:
            return None

def setup_google_sheets():
    """Setup Google Sheets API client"""
    try:
        credentials_json = base64.b64decode(os.environ['GOOGLE_CREDENTIALS']).decode('utf-8')
        credentials_dict = json.loads(credentials_json)
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Failed to setup Google Sheets: {str(e)}")
        raise

def update_spreadsheet(service, data):
    """Update Google Spreadsheet with follower counts"""
    try:
        spreadsheet_id = os.environ['SPREADSHEET_ID']
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        values = [[date] + [str(count) if count is not None else 'N/A' for count in data]]
        
        body = {
            'values': values
        }
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A:Z',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        logger.info(f"Data updated successfully at {date}")
        return True
    except Exception as e:
        logger.error(f"Error updating spreadsheet: {str(e)}")
        raise

def main():
    logger.info("Starting Instagram follower tracking...")
    
    try:
        username = os.environ['IG_USERNAME']
        password = os.environ['IG_PASSWORD']
        
        logger.info("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        logger.info(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        with InstagramScraper(username, password) as scraper:
            scraper.login()
            
            follower_counts = []
            for account in accounts:
                count = scraper.get_follower_count(account)
                follower_counts.append(count)
                time.sleep(random.uniform(2, 4))  # Random delay between accounts
        
        logger.info("Updating Google Spreadsheet...")
        update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()

