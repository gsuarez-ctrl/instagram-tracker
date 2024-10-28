import os
import json
import time
import random
import logging
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
        self.browser = self.playwright.firefox.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self):
        """Login to Instagram"""
        try:
            logger.info("Navigating to Instagram login page...")
            self.page.goto('https://www.instagram.com/accounts/login/')
            time.sleep(random.uniform(2, 4))

            # Accept cookies if the dialog appears
            try:
                self.page.click('text=Accept')
            except:
                pass

            logger.info("Entering login credentials...")
            self.page.fill('input[name="username"]', self.username)
            self.page.fill('input[name="password"]', self.password)
            
            time.sleep(random.uniform(1, 2))
            self.page.click('button[type="submit"]')
            
            # Wait for navigation
            self.page.wait_for_load_state('networkidle')
            time.sleep(random.uniform(3, 5))

            # Check if login was successful
            if '/accounts/onetap/' in self.page.url or '/accounts/login/' not in self.page.url:
                logger.info("Successfully logged in to Instagram")
                return True
            else:
                raise Exception("Login failed - redirected to login page")

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def get_follower_count(self, username):
        """Get follower count for a specific account"""
        try:
            # Navigate to user profile
            logger.info(f"Navigating to {username}'s profile...")
            self.page.goto(f'https://www.instagram.com/{username}/')
            time.sleep(random.uniform(2, 4))

            # Wait for follower count to be visible
            follower_element = self.page.wait_for_selector('a[href$="/followers/"] span')
            follower_text = follower_element.inner_text()
            
            # Convert text to number
            follower_count = self._convert_count(follower_text)
            logger.info(f"Successfully retrieved follower count for {username}: {follower_count}")
            return follower_count

        except Exception as e:
            logger.error(f"Error getting followers for {username}: {str(e)}")
            return None

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number"""
        try:
            count_text = count_text.replace(',', '').replace('.', '').lower()
            if 'k' in count_text:
                count = float(count_text.replace('k', '')) * 1000
            elif 'm' in count_text:
                count = float(count_text.replace('m', '')) * 1000000
            else:
                count = int(count_text)
            return int(count)
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
