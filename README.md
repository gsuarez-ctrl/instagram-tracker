## Instagram Follower Tracker

Automated tool to track Instagram followers for multiple accounts and store data in Google Sheets. Runs twice a week (Monday and Wednesday) using GitHub Actions.

## Features
- Automatically tracks follower counts on Monday and Wednesday at 9 AM UTC
- Stores data in Google Sheets with timestamps
- Runs using GitHub Actions (100% free)
- Includes error handling and retry logic
- Detailed logging for troubleshooting

## Setup Instructions

### 1. GitHub Repository Setup
1. Fork or clone this repository
2. Make sure it's public (required for free GitHub Actions)

### 2. Google Sheets Setup
1. Create a new Google Spreadsheet
2. Add headers in the first row:
   - Column A: "Date"
   - Following columns: Names of Instagram accounts you're tracking
3. Copy the spreadsheet ID from the URL (the long string between 'd/' and '/edit')

### 3. Google Cloud Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Google Sheets API
4. Create a Service Account:
   - Go to IAM & Admin > Service Accounts
   - Create a new service account
   - Download the JSON key file
5. Share your Google Sheet with the service account email

### 4. GitHub Secrets Setup
Add the following secrets to your repository (Settings > Secrets and variables > Actions):
1. `IG_USERNAME`: Your Instagram username
2. `IG_PASSWORD`: Your Instagram password
3. `SPREADSHEET_ID`: Your Google Sheet ID
4. `ACCOUNTS_TO_TRACK`: JSON array of Instagram accounts to track, e.g., `["instagram", "facebook", "twitter"]`
5. `GOOGLE_CREDENTIALS`: Your base64-encoded service account JSON

To encode Google credentials:
1. Open the downloaded JSON key file
2. Go to [base64encode.org](https://www.base64encode.org/)
3. Paste the JSON content and encode
4. Copy the encoded text to the `GOOGLE_CREDENTIALS` secret

### 5. Testing
1. Go to Actions tab in your repository
2. Enable workflows if prompted
3. Select "Instagram Follower Tracker"
4. Click "Run workflow"
5. Check your Google Sheet for the data

## Troubleshooting
Check the Actions tab for detailed logs if something goes wrong. Common issues:
- Invalid Instagram credentials
- Incorrect Google Sheet permissions
- Rate limiting from Instagram
- Malformed JSON in ACCOUNTS_TO_TRACK

## Support
If you encounter any issues:
1. Check the Actions logs
2. Verify all secrets are set correctly
3. Ensure Google Sheet permissions are set
4. Create an issue in this repository

## License
MIT License - feel free to modify and use as needed!

## Setup as personal with @gmail.com

## Updated to Feb 10 2025.
