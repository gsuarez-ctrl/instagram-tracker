import os
import json
import time
import random
import logging
from datetime import datetime
import instaloader
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64
import requests
import pickle

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, session_cookie):
        self.session_cookie = session_cookie
        self.loader = None
        self.init_loader()

    def init_loader(self):
        """Initialize a new Instaloader instance"""
        self.loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        # Create a new session
        self.loader.context._session = requests.Session()
        
        # Set up session with cookie
        self.loader.context._session.cookies.set(
            'sessionid', 
            self.session_cookie, 
            domain='.instagram.com'
        )
        
        # Set up headers
        self.loader.context._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def get_follower_count(self, username):
        """Get follower count for a specific account"""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Getting follower count for {username} (attempt {attempt + 1}/{max_retries})...")
                profile = instaloader.Profile.from_username(self.loader.context, username)
                count = profile.followers
                logger.info(f"Found follower count for {username}: {count}")
                return count

            except instaloader.exceptions.ProfileNotExistsException:
                logger.error(f"Profile {username} does not exist")
                return None
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {username}: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Reinitialize loader with new session before retry
                    self.init_loader()
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error(f"Error getting followers for {username} after {max_retries} attempts: {str(e)}")
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
            range='followers!A:Z',
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
        session_cookie = os.environ['IG_SESSION_COOKIE']
        
        # Setup Google Sheets
        logger.info("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        # Get accounts to track
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        logger.info(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        # Initialize scraper
        scraper = InstagramScraper(session_cookie)
        
        # Get follower counts with retry mechanism
        follower_counts = []
        for i, account in enumerate(accounts):
            try:
                count = scraper.get_follower_count(account)
                follower_counts.append(count)
                
                # Add longer delays every few accounts to avoid rate limiting
                if (i + 1) % 3 == 0:
                    logger.info("Taking a longer break to avoid rate limiting...")
                    time.sleep(random.uniform(20, 25))
                else:
                    time.sleep(random.uniform(8, 12))  # Increased delay between requests
                    
            except Exception as e:
                logger.error(f"Failed to get count for {account}: {str(e)}")
                follower_counts.append(None)
                time.sleep(15)  # Additional delay after error
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
