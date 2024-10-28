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
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def wait_and_retry(self, action, max_attempts=3, timeout=30000):
        """Helper method to wait and retry actions"""
        for attempt in range(max_attempts):
            try:
                return action()
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(3)

    def login(self):
        """Login to Instagram with enhanced error handling"""
        try:
            logger.info("Navigating to Instagram login page...")
            
            # Direct navigation to login page
            self.wait_and_retry(
                lambda: self.page.goto('https://www.instagram.com/accounts/login/', 
                wait_until='domcontentloaded', timeout=30000)
            )
            time.sleep(3)

            logger.info("Waiting for login form...")
            def find_login_form():
                username_field = self.page.wait_for_selector('input[name="username"]', timeout=10000)
                if not username_field:
                    raise Exception("Username field not found")
                return username_field

            username_field = self.wait_and_retry(find_login_form)

            logger.info("Entering login credentials...")
            def enter_credentials():
                # Fill username
                username_field.fill(self.username)
                time.sleep(1)
                
                # Fill password
                password_field = self.page.wait_for_selector('input[name="password"]', timeout=10000)
                password_field.fill(self.password)
                time.sleep(1)
                
                # Click login button
                submit_button = self.page.wait_for_selector('button[type="submit"]', timeout=10000)
                submit_button.click()
                return True

            self.wait_and_retry(enter_credentials)
            time.sleep(5)  # Wait for login process

            # Enhanced login verification with multiple checks
            def verify_login():
                success_indicators = [
                    lambda: bool(self.page.query_selector('svg[aria-label="Home"]')),
                    lambda: bool(self.page.query_selector('[aria-label="Search"]')),
                    lambda: bool(self.page.query_selector('[aria-label="Direct messaging"]')),
                    lambda: bool(self.page.query_selector('[aria-label="New post"]')),
                    lambda: not bool(self.page.query_selector('input[name="username"]')),
                    lambda: 'login' not in self.page.url
                ]

                return any(indicator() for indicator in success_indicators)

            login_success = self.wait_and_retry(verify_login)
            
            if not login_success:
                self.page.screenshot(path='login_failed.png')
                raise Exception("Could not verify successful login")

            logger.info("Successfully logged in to Instagram")
            time.sleep(2)
            return True

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            try:
                self.page.screenshot(path='login_error.png')
            except:
                pass
            raise

    def get_follower_count(self, username):
        """Get follower count for a specific account with enhanced extraction methods"""
        try:
            logger.info(f"Getting follower count for {username}...")
            
            # Load profile
            def load_profile():
                self.page.goto(f'https://www.instagram.com/{username}/', 
                    wait_until='domcontentloaded', timeout=15000)
                time.sleep(3)
                
                # Check if profile exists
                if "Sorry, this page isn't available." in self.page.content():
                    raise Exception("Profile not found")
                
                return self.page.content()

            # Load profile with retry mechanism
            content = self.wait_and_retry(load_profile)

            # Method 1: Try meta tags first
            meta_selectors = [
                'meta[name="description"]',
                'meta[property="og:description"]'
            ]
            for selector in meta_selectors:
                try:
                    element = self.page.query_selector(selector)
                    if element:
                        content = element.get_attribute('content')
                        match = re.search(r'([\d,\.]+[KkMm]?)\s*(?:Followers|followers)', content)
                        if match:
                            count = self._convert_count(match.group(1))
                            if count:
                                logger.info(f"Found follower count from meta: {count}")
                                return count
                except Exception as e:
                    logger.debug(f"Meta extraction failed: {str(e)}")

            # Method 2: Try visible elements
            element_selectors = [
                'header section ul li span span',  # New profile layout
                'a[href*="followers"] span span',  # Follower link with nested spans
                '[role="button"]:has-text("followers")',  # Button with followers text
                'span[title*="followers"]',  # Span with followers in title
                '//a[contains(@href, "followers")]/span/span',  # XPath for nested spans
                '//div[contains(@class, "_ac2a")]/span/span'  # Class-based selector
            ]

            for selector in element_selectors:
                try:
                    if selector.startswith('//'):
                        elements = self.page.locator(selector).all()
                    else:
                        elements = self.page.query_selector_all(selector)
                    
                    for element in elements:
                        text = element.inner_text()
                        if text:
                            count = self._convert_count(text)
                            if count:
                                logger.info(f"Found follower count from element: {count}")
                                return count
                except Exception as e:
                    logger.debug(f"Element extraction failed: {str(e)}")

            # Method 3: Try page source
            try:
                patterns = [
                    r'"edge_followed_by":\{"count":(\d+)\}',
                    r'"followers":(\d+)',
                    r'Followers":"([\d,]+)"',
                    r'([\d,\.]+[KkMm]?)\s*Followers'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        for match in matches:
                            count = self._convert_count(match)
                            if count:
                                logger.info(f"Found follower count from source: {count}")
                                return count
            except Exception as e:
                logger.debug(f"Source extraction failed: {str(e)}")

            # Save debug screenshot if all methods fail
            self.page.screenshot(path=f'debug_{username}.png')
            logger.error(f"Could not find follower count for {username}")
            return None

        except Exception as e:
            logger.error(f"Error getting followers for {username}: {str(e)}")
            try:
                self.page.screenshot(path=f'error_{username}.png')
            except:
                pass
            return None

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number with enhanced parsing"""
        try:
            # Clean and standardize the text
            count_text = str(count_text).strip().replace(',', '').replace(' ', '')
            count_text = count_text.lower()

            # Handle different formats
            multiplier = 1
            if 'k' in count_text:
                multiplier = 1000
                count_text = count_text.replace('k', '')
            elif 'm' in count_text:
                multiplier = 1000000
                count_text = count_text.replace('m', '')

            # Convert to number
            if '.' in count_text:
                number = float(count_text) * multiplier
            else:
                number = float(count_text) * multiplier

            result = int(round(number))
            if result > 0:
                return result
            return None

        except Exception as e:
            logger.debug(f"Error converting count text '{count_text}': {str(e)}")
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
            scraper.login()
            
            # Get follower counts
            follower_counts = []
            for account in accounts:
                count = scraper.get_follower_count(account)
                follower_counts.append(count)
                time.sleep(random.uniform(2, 4))  # Random delay between accounts
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
