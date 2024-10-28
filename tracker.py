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
import pickle
import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, session_cookie):
        self.session_cookie = session_cookie
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

    def login_with_session(self):
        """Login to Instagram using session cookie"""
        try:
            logger.info("Logging in to Instagram using session cookie...")
            
            # Set session cookie
            self.loader.context.session.cookies.set(
                'sessionid',
                self.session_cookie,
                domain='.instagram.com'
            )
            
            # Verify session is working
            try:
                test_profile = instaloader.Profile.from_username(self.loader.context, "instagram")
                if test_profile.followers > 0:
                    logger.info("Successfully logged in to Instagram")
                    return True
            except Exception as e:
                logger.error(f"Session verification failed: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def get_follower_count(self, username):
        """Get follower count for a specific account"""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Getting follower count for {username} (attempt {attempt + 1}/{max_retries})...")
                
                # Get profile info
                profile = instaloader.Profile.from_username(self.loader.context, username)
                count = profile.followers
                
                logger.info(f"Found follower count for {username}: {count}")
                return count

            except instaloader.exceptions.ProfileNotExistsException:
                logger.error(f"Profile {username} does not exist")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed for {username}: {str(e)}")
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
        session_cookie = os.environ['IG_SESSION_COOKIE']
        
        # Setup Google Sheets
        logger.info("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        # Get accounts to track
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        logger.info(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        # Initialize scraper and login
        scraper = InstagramScraper(session_cookie)
        scraper.login_with_session()
        
        # Get follower counts with retry mechanism
        follower_counts = []
        for account in accounts:
            try:
                count = scraper.get_follower_count(account)
                follower_counts.append(count)
                # Random delay between requests to avoid rate limiting
                time.sleep(random.uniform(3, 5))
            except Exception as e:
                logger.error(f"Failed to get count for {account}: {str(e)}")
                follower_counts.append(None)
                time.sleep(5)  # Additional delay after error
        
        # Update spreadsheet
        logger.info("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        logger.info("Script completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
