import os
import json
import time
import random
import logging
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

    def wait_and_click(self, selector, timeout=30000):
        """Wait for element and click it"""
        try:
            element = self.page.wait_for_selector(selector, timeout=timeout)
            element.click()
            return True
        except Exception as e:
            logger.error(f"Error clicking element {selector}: {str(e)}")
            return False

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

            # Click on login if we're on the main page
            try:
                login_button = self.page.get_by_text('Log in')
                if login_button:
                    login_button.click()
                    time.sleep(2)
            except:
                pass

            logger.info("Entering login credentials...")
            
            # Wait for username field and enter username
            username_field = self.page.wait_for_selector('input[name="username"]', timeout=10000)
            username_field.fill(self.username)
            time.sleep(random.uniform(0.5, 1.5))

            # Enter password
            password_field = self.page.wait_for_selector('input[name="password"]')
            password_field.fill(self.password)
            time.sleep(random.uniform(0.5, 1.5))

            # Click login button
            login_button = self.page.wait_for_selector('button[type="submit"]')
            login_button.click()
            
            # Wait for navigation and check for successful login
            time.sleep(5)  # Wait for potential redirects

            # Check for various success indicators
            success = False
            try:
                # Check for common success indicators
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
                logger.error("Login unsuccessful - could not verify success indicators")
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
        """Get follower count for a specific account with enhanced error handling"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Navigate to profile
                logger.info(f"Navigating to {username}'s profile...")
                self.page.goto(f'https://www.instagram.com/{username}/', wait_until='networkidle')
                time.sleep(random.uniform(3, 5))

                # Look for the followers count with multiple selector options
                selectors = [
                    'a[href$="/followers/"] span',
                    'a[href*="followers"] span',
                    '[data-testid="profile-stats"] span',
                    'ul li span span',
                ]

                follower_count = None
                for selector in selectors:
                    try:
                        element = self.page.wait_for_selector(selector, timeout=5000)
                        if element:
                            text = element.inner_text()
                            if any(char.isdigit() for char in text):
                                follower_count = self._convert_count(text)
                                break
                    except:
                        continue

                if follower_count is not None:
                    logger.info(f"Successfully retrieved follower count for {username}: {follower_count}")
                    return follower_count
                
                raise Exception("Could not find follower count")

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Error getting followers for {username} after {max_retries} attempts: {str(e)}")
                    return None
                logger.warning(f"Attempt {attempt + 1} failed for {username}, retrying...")
                time.sleep(5 * (attempt + 1))

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number"""
        try:
            count_text = count_text.replace(',', '').replace('.', '').lower().strip()
            multiplier = 1
            
            if 'k' in count_text:
                count_text = count_text.replace('k', '')
                multiplier = 1000
            elif 'm' in count_text:
                count_text = count_text.replace('m', '')
                multiplier = 1000000
            
            # Handle decimal points in K/M numbers
            if '.' in count_text:
                base = float(count_text)
            else:
                base = int(count_text)
                
            return int(base * multiplier)
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
        # Initialize variables
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
                time.sleep(random.uniform(3, 5))  # Random delay between requests
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
