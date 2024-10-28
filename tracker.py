# tracker.py
import os
import json
from instagrapi import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import time
import base64

def setup_instagram_client():
    """Initialize and login to Instagram client"""
    try:
        cl = Client()
        cl.login(os.environ['IG_USERNAME'], os.environ['IG_PASSWORD'])
        return cl
    except Exception as e:
        print(f"Failed to login to Instagram: {str(e)}")
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
        print(f"Failed to setup Google Sheets: {str(e)}")
        raise

def get_follower_count(client, username):
    """Get follower count for a specific Instagram account"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            user_id = client.user_id_from_username(username)
            user_info = client.user_info(user_id)
            return user_info.follower_count
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error getting followers for {username} after {max_retries} attempts: {str(e)}")
                return None
            time.sleep(5)  # Wait 5 seconds before retrying

def update_spreadsheet(service, data):
    """Update Google Spreadsheet with follower counts"""
    try:
        spreadsheet_id = os.environ['SPREADSHEET_ID']
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        values = [[date] + data]
        
        body = {
            'values': values
        }
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A:Z',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        print(f"Data updated successfully at {date}")
        return True
    except Exception as e:
        print(f"Error updating spreadsheet: {str(e)}")
        raise

def main():
    print("Starting Instagram follower tracking...")
    
    try:
        # Initialize clients
        print("Setting up Instagram client...")
        ig_client = setup_instagram_client()
        
        print("Setting up Google Sheets client...")
        sheets_service = setup_google_sheets()
        
        # Get accounts to track
        accounts = json.loads(os.environ['ACCOUNTS_TO_TRACK'])
        print(f"Tracking {len(accounts)} accounts: {', '.join(accounts)}")
        
        # Get follower counts
        follower_counts = []
        for account in accounts:
            print(f"Getting follower count for {account}...")
            count = get_follower_count(ig_client, account)
            follower_counts.append(count)
            time.sleep(3)  # Avoid rate limiting
        
        # Update spreadsheet
        print("Updating Google Spreadsheet...")
        success = update_spreadsheet(sheets_service, follower_counts)
        
        print("Script completed successfully!")
        
    except Exception as e:
        print(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
