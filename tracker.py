import os
import json
import time
import random
import logging
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import base64
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.csrf_token = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
    def login(self):
        """Login to Instagram"""
        try:
            # Get the initial csrf token
            logger.info("Getting initial CSRF token...")
            initial_response = self.session.get('https://www.instagram.com/accounts/login/', headers=self.headers)
            csrf_pattern = re.compile(r'"csrf_token":"([^"]+)"')
            csrf_match = csrf_pattern.search(initial_response.text)
            if csrf_match:
                self.csrf_token = csrf_match.group(1)
            
            # Update headers with csrf token
            self.headers.update({
                'X-CSRFToken': self.csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.instagram.com/accounts/login/',
                'Origin': 'https://www.instagram.com'
            })
            
            # Prepare login data
            login_data = {
                'username': self.username,
                'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{self.password}',
                'queryParams': {},
                'optIntoOneTap': 'false'
            }
            
            # Perform login
            logger.info("Attempting to login...")
            login_response = self.session.post(
                'https://www.instagram.com/accounts/login/ajax/',
                data=login_data,
                headers=self.headers,
                allow_redirects=True
            )
            
            if login_response.json().get('authenticated'):
                logger.info("Successfully logged in to Instagram")
                return True
            else:
                raise Exception(f"Login failed: {login_response.text}")
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def get_follower_count(self, username):
        """Get follower count for a specific account"""
        try:
            # Add random delay
            time.sleep(random.uniform(2, 4))
            
            # Get user page
            response = self.session.get(
                f'https://www.instagram.com/{username}/?__a=1&__d=dis',
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'graphql' in data:
                    user_data = data['graphql']['user']
                    return user_data['edge_followed_by']['count']
            
            raise Exception(f"Could not get follower count for {username}")
            
        except Exception as e:
            logger.error(f"Error getting followers for {username}: {str(e)}")
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
        # Initialize Instagram scraper
        username = os.environ['IG_USERNAME']
        password = os.environ['IG_PASSWORD']
        
        logger.info("Setting up Instagram scraper...")
        scraper = InstagramScraper(username, password)
        scraper.login()
        
        # Setup Google Sheets
        logger.info("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        # Get accounts to track
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        logger.info(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        # Get follower counts
        follower_counts = []
        for account in accounts:
            logger.info(f"Getting follower count for {account}...")
            count = scraper.get_follower_count(account)
            follower_counts.append(count)
            time.sleep(random.uniform(3, 5))  # Random delay between accounts
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
