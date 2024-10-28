import os
import logging
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.browser = None
        self.page = None

    def __enter__(self):
        logger.info("Setting up Playwright...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        self.playwright.stop()

    def login(self):
        logger.info("Navigating to Instagram login page...")
        self.page.goto("https://www.instagram.com/accounts/login/")
        logger.info("Entering login credentials...")
        self.page.fill("input[name='username']", self.username)
        self.page.fill("input[name='password']", self.password)
        self.page.click("button[type='submit']")
        logger.info("Successfully logged in to Instagram")

    def get_follower_count(self, username):
        logger.info(f"Getting follower count for {username}...")
        self.page.goto(f"https://www.instagram.com/{username}/")
        # Aquí se debe implementar la lógica para obtener el conteo de seguidores
        try:
            followers = self.page.query_selector('a[href$="/followers/"] > span').inner_text()
            return int(followers.replace(',', ''))
        except Exception as e:
            logger.error(f"Error getting followers for {username}: {e}")
            return None

def main():
    logger.info("Starting Instagram follower tracking...")
    username = os.environ.get('IG_USERNAME')
    password = os.environ.get('IG_PASSWORD')
    accounts_to_track = os.environ.get('ACCOUNTS_TO_TRACK').split(',')

    with InstagramScraper(username, password) as scraper:
        for account in accounts_to_track:
            count = scraper.get_follower_count(account.strip())
            if count is not None:
                logger.info(f"{account.strip()} has {count} followers.")

if __name__ == "__main__":
    main()

