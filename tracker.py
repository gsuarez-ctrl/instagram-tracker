import os
import json
import time
import random
import logging
from instagram_private_api import Client, ClientCompatPatch
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_instagram_client():
    """Initialize and login to Instagram client"""
    try:
        username = os.environ['IG_USERNAME']
        password = os.environ['IG_PASSWORD']
        
        logger.info("Attempting to login to Instagram...")
        
        # Initialize client with more realistic device settings
        settings = {
            'device_string': '28/9.0; 640dpi; 1440x2560; samsung; SM-G965F',
            'guid': str(random.randint(1000000000, 9999999999)),
            'phone_id': str(random.randint(1000000000, 9999999999)),
            'user_agent': 'Instagram 269.0.0.18.75 Android'
        }
        
        api = Client(username, password, **settings)
        logger.info("Successfully logged in to Instagram")
        return api
        
    except Exception as e:
        logger.error(f"Failed to login to Instagram: {str(e)}")
        raise

def get_follower_count(client, username, max_retries=3):
    """Get follower count for a specific Instagram account"""
    for attempt in range(max_retries):
        try:
            # Add random delay between requests
            time.sleep(random.uniform(2, 4))
            
            # Get user info
            user_info = client.username_info(username)
            follower_count = user_info['user']['follower_count']
            logger.info(f"Successfully retrieved follower count for {username}")
            return follower_count
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Error getting followers for {username} after {max_retries} attempts: {str(e)}")
                return None
            logger.warning(f"Attempt {attempt + 1} failed for {username}, retrying...")
            time.sleep(5 * (attempt + 1))  # Exponential backoff

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

def main():
    logger.info("Starting Instagram follower tracking...")
    
    try:
        # Initialize clients
        logger.info("Setting up Instagram client...")
        ig_client = setup_instagram_client()
        
        logger.info("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        # Get accounts to track
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        logger.info(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        # Get follower counts
        follower_counts = []
        for account in accounts:
            logger.info(f"Getting follower count for {account}...")
            count = get_follower_count(ig_client, account)
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
