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
            self.page.goto('https://www.instagram.com/accounts/login/', timeout=20000)
            time.sleep(2)

            logger.info("Entering login credentials...")
            # Enter username
            username_field = self.page.wait_for_selector('input[name="username"]', timeout=5000)
            username_field.fill(self.username)
            time.sleep(1)

            # Enter password
            password_field = self.page.wait_for_selector('input[name="password"]')
            password_field.fill(self.password)
            time.sleep(1)

            # Click login button
            self.page.click('button[type="submit"]')
            time.sleep(3)

            # Verify login success
            self.page.wait_for_selector('div[role="menuitem"]', timeout=10000)
            logger.info("Successfully logged in to Instagram")
            return True

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def get_follower_count_from_html(self, html_content):
        """Extract follower count from HTML content using various methods"""
        try:
            # Try JSON data pattern
            json_match = re.search(r'"edge_followed_by":\{"count":(\d+)\}', html_content)
            if json_match:
                return int(json_match.group(1))

            # Try meta description pattern
            meta_match = re.search(r'([\d,.]+)\s*Followers', html_content)
            if meta_match:
                return self._convert_count(meta_match.group(1))

            # Try numeric patterns near "followers"
            follower_matches = re.findall(r'([\d,.]+)[kK]?\s*(?:Followers|followers)', html_content)
            if follower_matches:
                return self._convert_count(follower_matches[0])

            return None
        except Exception as e:
            logger.error(f"Error extracting follower count from HTML: {str(e)}")
            return None

    def get_follower_count(self, username):
        """Get follower count for a specific account"""
        try:
            logger.info(f"Getting follower count for {username}...")
            
            # Navigate to profile with shorter timeout
            self.page.goto(f'https://www.instagram.com/{username}/', timeout=15000)
            time.sleep(2)

            # Get page content immediately
            content = self.page.content()

            # Check if profile exists
            if "Sorry, this page isn't available." in content:
                logger.error(f"Profile {username} not found")
                return None

            # Try to get follower count from HTML first
            count = self.get_follower_count_from_html(content)
            if count is not None:
                logger.info(f"Found follower count for {username}: {count}")
                return count

            # If HTML parsing failed, try visible elements with very short timeout
            try:
                follower_element = self.page.wait_for_selector(
                    'a[href*="followers"] span, span[title$="followers"]',
                    timeout=5000
                )
                if follower_element:
                    count = self._convert_count(follower_element.inner_text())
                    if count is not None:
                        logger.info(f"Found follower count for {username}: {count}")
                        return count
            except:
                pass

            logger.error(f"Could not find follower count for {username}")
            return None

        except Exception as e:
            logger.error(f"Error getting followers for {username}: {str(e)}")
            return None

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number"""
        try:
            # Remove any non-numeric characters except K, M, k, m, and decimal point
            count_text = count_text.strip().replace(',', '')
            
            # Convert to lowercase for consistency
            count_text = count_text.lower()
            
            # Handle K (thousands)
            if 'k' in count_text:
                number = float(count_text.replace('k', '')) * 1000
            # Handle M (millions)
            elif 'm' in count_text:
                number = float(count_text.replace('m', '')) * 1000000
            # Handle regular numbers
            else:
                number = float(count_text)
            
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
            scraper.login()
            
            # Get follower counts
            follower_counts = []
            for account in accounts:
                count = scraper.get_follower_count(account)
                follower_counts.append(count)
                time.sleep(1)  # Brief delay between accounts
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
