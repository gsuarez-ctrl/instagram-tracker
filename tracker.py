import os
import json
import time
import random
import logging
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
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
        self.browser = self.playwright.firefox.launch(
            headless=True,
            firefox_user_prefs={
                "media.autoplay.default": 2,
                "media.autoplay.blocking_policy": 2
            }
        )
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self):
        """Login to Instagram with enhanced error handling"""
        try:
            logger.info("Navigating to Instagram login page...")
            self.page.goto('https://www.instagram.com/', wait_until='networkidle')
            time.sleep(random.uniform(3, 5))

            # Handle cookie acceptance if present
            try:
                cookie_button = self.page.get_by_role("button", name="Allow all cookies")
                if cookie_button:
                    cookie_button.click()
                    time.sleep(2)
            except:
                pass

            # Handle "Log in" button if present
            try:
                login_button = self.page.get_by_text('Log in')
                if login_button:
                    login_button.click()
                    time.sleep(2)
            except:
                pass

            logger.info("Entering login credentials...")
            
            # Enter username
            username_field = self.page.wait_for_selector('input[name="username"]', timeout=10000)
            username_field.fill(self.username)
            time.sleep(random.uniform(0.5, 1.5))

            # Enter password
            password_field = self.page.wait_for_selector('input[name="password"]')
            password_field.fill(self.password)
            time.sleep(random.uniform(0.5, 1.5))

            # Click login button
            self.page.wait_for_selector('button[type="submit"]').click()
            time.sleep(5)

            # Check for successful login
            success = False
            try:
                success_indicators = [
                    lambda: 'instagram.com/accounts/onetap/' in self.page.url,
                    lambda: 'instagram.com/' == self.page.url,
                    lambda: self.page.query_selector('nav') is not None,
                    lambda: self.page.query_selector('[data-testid="user-avatar"]') is not None,
                    lambda: not self.page.query_selector('input[name="username"]')
                ]
                
                for indicator in success_indicators:
                    if indicator():
                        success = True
                        break

            except Exception as e:
                logger.error(f"Error checking login status: {str(e)}")

            if not success:
                logger.error("Login unsuccessful")
                self.page.screenshot(path='login_failed.png')
                raise Exception("Login verification failed")

            logger.info("Successfully logged in to Instagram")
            return True

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            try:
                self.page.screenshot(path='error_screenshot.png')
            except:
                pass
            raise

    def get_follower_count(self, username):
        """Get follower count for a specific account"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to {username}'s profile...")
                self.page.goto(f'https://www.instagram.com/{username}/', wait_until='networkidle')
                time.sleep(random.uniform(3, 5))

                # Wait for content to load
                self.page.wait_for_load_state('networkidle')

                # Try multiple methods to get follower count
                methods = [
                    self._get_followers_from_meta,
                    self._get_followers_from_elements,
                    self._get_followers_from_html
                ]

                for method in methods:
                    try:
                        count = method(username)
                        if count is not None:
                            logger.info(f"Successfully retrieved follower count for {username}: {count}")
                            return count
                    except Exception as e:
                        logger.debug(f"Method failed: {str(e)}")
                        continue

                # If we get here, save screenshot and retry
                self.page.screenshot(path=f'debug_{username}_{attempt}.png')
                raise Exception("Could not find follower count")

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Error getting followers for {username} after {max_retries} attempts: {str(e)}")
                    return None
                logger.warning(f"Attempt {attempt + 1} failed for {username}, retrying...")
                time.sleep(5 * (attempt + 1))

    def _get_followers_from_meta(self, username):
        """Get follower count from meta tag"""
        meta_content = self.page.get_attribute('meta[property="og:description"]', 'content')
        if meta_content:
            matches = re.findall(r'([\d,]+)\s+Followers', meta_content)
            if matches:
                return self._convert_count(matches[0])
        return None

    def _get_followers_from_elements(self, username):
        """Get follower count from page elements"""
        selectors = [
            'a[href$="/followers/"] span',
            'a[href*="followers"] span',
            'ul li span span',
            '//section//ul//span[contains(text(), "followers")]/parent::*/span',
            '//div[contains(@class, "_ac2a")]/span/span'
        ]

        for selector in selectors:
            try:
                if selector.startswith('//'):
                    element = self.page.locator(selector).first
                else:
                    element = self.page.locator(selector).first
                
                if element:
                    text = element.inner_text()
                    if any(char.isdigit() for char in text):
                        return self._convert_count(text)
            except:
                continue
        return None

    def _get_followers_from_html(self, username):
        """Get follower count from page HTML"""
        content = self.page.content()
        matches = re.findall(r'"edge_followed_by":{"count":(\d+)}', content)
        if matches:
            return int(matches[0])
        return None

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number"""
        try:
            count_text = count_text.strip().replace(',', '').replace(' ', '').lower()
            
            multiplier = 1
            if 'k' in count_text:
                multiplier = 1000
                count_text = count_text.replace('k', '')
            elif 'm' in count_text:
                multiplier = 1000000
                count_text = count_text.replace('m', '')
                
            if '.' in count_text:
                number = float(count_text) * multiplier
            else:
                number = int(count_text) * multiplier
                
            return int(round(number))
            
        except Exception as e:
            logger.error(f"Error converting count text '{count_text}': {str(e)}")
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
        
        # Setup Google Sheets
        logger.info("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        # Get accounts to track
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        logger.info(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        # Initialize scraper and get follower counts
        with InstagramScraper(username, password) as scraper:
            logger.info("Setting up Instagram scraper...")
            scraper.login()
            
            # Get follower counts
            follower_counts = []
            for account in accounts:
                logger.info(f"Getting follower count for {account}...")
                count = scraper.get_follower_count(account)
                follower_counts.append(count)
                time.sleep(random.uniform(3, 5))
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
