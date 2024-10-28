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
                wait_until='networkidle', timeout=30000)
            )
            time.sleep(4)

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
                    lambda: bool(self.page.query_selector('svg[aria-label="New post"]')),
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
        """Get follower count for a specific account"""
        try:
            logger.info(f"Getting follower count for {username}...")
            
            # Load profile with proper waiting
            def load_profile():
                self.page.goto(f'https://www.instagram.com/{username}/', wait_until='networkidle')
                time.sleep(4)  # Additional wait for dynamic content
                return True

            self.wait_and_retry(load_profile)

            # Use JavaScript to extract follower count - this handles the dynamic layout better
            follower_count = self.page.evaluate('''() => {
                // Function to parse count text
                function parseCount(text) {
                    if (!text) return null;
                    text = text.toLowerCase().replace(/,/g, '');
                    let multiplier = 1;
                    if (text.includes('k')) {
                        multiplier = 1000;
                        text = text.replace('k', '');
                    } else if (text.includes('m')) {
                        multiplier = 1000000;
                        text = text.replace('m', '');
                    }
                    return Math.round(parseFloat(text) * multiplier);
                }

                // Try various methods to find the follower count
                let count;

                // Method 1: Try meta description
                const meta = document.querySelector('meta[name="description"]');
                if (meta) {
                    const match = meta.content.match(/([\d,.]+[KkMm]?)\s*Followers/);
                    if (match) {
                        count = parseCount(match[1]);
                        if (count) return count;
                    }
                }

                // Method 2: Try section stats
                const stats = document.querySelectorAll('section ul li');
                for (const stat of stats) {
                    if (stat.textContent.includes('follower')) {
                        const text = stat.textContent.match(/([\d,.]+[KkMm]?)/);
                        if (text) {
                            count = parseCount(text[1]);
                            if (count) return count;
                        }
                    }
                }

                // Method 3: Try flex layout containers
                const flexContainers = document.querySelectorAll('div[style*="flex"]');
                for (const container of flexContainers) {
                    if (container.textContent.includes('follower')) {
                        const text = container.textContent.match(/([\d,.]+[KkMm]?)\s*follower/i);
                        if (text) {
                            count = parseCount(text[1]);
                            if (count) return count;
                        }
                    }
                }

                // Method 4: Try any element containing followers text
                const allElements = document.querySelectorAll('*');
                for (const element of allElements) {
                    if (element.textContent.includes('follower')) {
                        const text = element.textContent.match(/([\d,.]+[KkMm]?)\s*follower/i);
                        if (text) {
                            count = parseCount(text[1]);
                            if (count) return count;
                        }
                    }
                }

                return null;
            }''')

            if follower_count:
                logger.info(f"Found follower count for {username}: {follower_count}")
                return follower_count

            # If JavaScript method fails, try backup method with Playwright selectors
            try:
                # Try various selectors
                selectors = [
                    'header section ul li span span',
                    'section ul li span span',
                    'div[role="tablist"] span span',
                    '[role="button"]:has-text("followers")'
                ]

                for selector in selectors:
                    element = self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        text = element.inner_text()
                        if 'follower' in text.lower():
                            # Extract number from text
                            match = re.search(r'([\d,\.]+[KkMm]?)', text)
                            if match:
                                count = self._convert_count(match.group(1))
                                if count:
                                    logger.info(f"Found follower count for {username}: {count}")
                                    return count
            except Exception as e:
                logger.debug(f"Backup extraction failed: {str(e)}")

            # Save debug information
            self.page.screenshot(path=f'debug_{username}.png')
            with open(f'debug_{username}.html', 'w', encoding='utf-8') as f:
                f.write(self.page.content())

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
        """Convert Instagram follower count text to number"""
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
            return result if result > 0 else None

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
