# [Previous imports remain the same...]

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
            time.sleep(5)  # Increased wait time after login

            # Multiple login verification attempts
            success = False
            try:
                # Try multiple selectors that indicate successful login
                success_selectors = [
                    'svg[aria-label="Home"]',
                    'a[href="/direct/inbox/"]',
                    'span[aria-label="Home"]',
                    'a[href^="/stories/"]',
                    '[aria-label="Home"]',
                    '[aria-label="Direct messaging"]'
                ]
                
                for selector in success_selectors:
                    try:
                        if self.page.wait_for_selector(selector, timeout=3000):
                            success = True
                            break
                    except:
                        continue

                if not success:
                    # Check if we're still on the login page
                    if self.page.query_selector('input[name="username"]'):
                        raise Exception("Still on login page")
                    
                    # Check URL
                    current_url = self.page.url
                    if 'login' not in current_url and 'instagram.com' in current_url:
                        success = True
            except Exception as e:
                logger.warning(f"Initial login check failed: {str(e)}")

            if success:
                logger.info("Successfully logged in to Instagram")
                time.sleep(2)  # Brief pause after successful login
                return True
            else:
                # Save screenshot for debugging
                self.page.screenshot(path='login_failed.png')
                raise Exception("Could not verify successful login")

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            try:
                self.page.screenshot(path='login_error.png')
            except:
                pass
            raise

# [Rest of the code remains exactly the same...]
