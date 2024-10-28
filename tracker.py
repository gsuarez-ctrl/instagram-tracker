[Previous imports and initial setup remain exactly the same until class InstagramScraper's get_follower_count method]

    def get_follower_count(self, username):
        """Get follower count for a specific account with enhanced extraction"""
        try:
            logger.info(f"Getting follower count for {username}...")
            
            def load_profile():
                self.page.goto(f'https://www.instagram.com/{username}/', 
                    wait_until='domcontentloaded', timeout=15000)
                # Wait for content to load
                time.sleep(3)
                return True

            # Load profile with retry mechanism
            self.wait_and_retry(load_profile)

            # Try multiple methods to find follower count
            selectors = [
                'li:has-text("followers") span span',
                'span:has-text("followers") span',
                'a[href*="followers"] span span',
                'a[href*="followers"] span',
                '[role="button"]:has-text("followers")',
                'meta[name="description"]'
            ]

            for selector in selectors:
                try:
                    if selector.startswith('meta'):
                        # Handle meta description separately
                        element = self.page.query_selector(selector)
                        if element:
                            content = element.get_attribute('content')
                            match = re.search(r'([\d,]+)\s+Followers', content)
                            if match:
                                count = self._convert_count(match.group(1))
                                if count is not None:
                                    logger.info(f"Found follower count for {username} (meta): {count}")
                                    return count
                    else:
                        # Try to find the element and get its text
                        element = self.page.wait_for_selector(selector, timeout=5000)
                        if element:
                            text = element.inner_text()
                            # Extract numbers from text
                            numbers = re.findall(r'[\d,\.]+[KkMm]?', text)
                            for num in numbers:
                                count = self._convert_count(num)
                                if count is not None:
                                    logger.info(f"Found follower count for {username} (element): {count}")
                                    return count
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {str(e)}")
                    continue

            # If above methods fail, try parsing the page source
            try:
                content = self.page.content()
                # Look for follower count in script tags
                script_patterns = [
                    r'"edge_followed_by":\{"count":(\d+)\}',
                    r'"followedBy":\{"count":(\d+)\}',
                    r'"followers":(\d+)',
                    r'Followers":(\d+)',
                ]
                
                for pattern in script_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        count = int(matches[0])
                        logger.info(f"Found follower count for {username} (script): {count}")
                        return count
            except Exception as e:
                logger.debug(f"Script parsing failed: {str(e)}")

            # Save debug screenshot
            try:
                self.page.screenshot(path=f'debug_{username}.png')
            except:
                pass

            logger.error(f"Could not find follower count for {username}")
            return None

        except Exception as e:
            logger.error(f"Error getting followers for {username}: {str(e)}")
            try:
                self.page.screenshot(path=f'error_{username}.png')
            except:
                pass
            return None

    def _convert_count(self, count_text):
        """Convert Instagram follower count text to number with enhanced parsing"""
        try:
            # Remove any non-numeric characters except K, M, k, m, and decimal point
            count_text = count_text.strip().replace(',', '')
            
            # Convert to lowercase for consistency
            count_text = count_text.lower()
            
            # Handle different formats
            multiplier = 1
            if 'k' in count_text:
                multiplier = 1000
                count_text = count_text.replace('k', '')
            elif 'm' in count_text:
                multiplier = 1000000
                count_text = count_text.replace('m', '')
            
            # Handle decimal points
            if '.' in count_text:
                number = float(count_text) * multiplier
            else:
                number = int(count_text) * multiplier
            
            result = int(round(number))
            if result > 0:  # Validate the result
                return result
            return None
            
        except Exception as e:
            logger.error(f"Error converting count text '{count_text}': {str(e)}")
            return None

[Rest of the code remains exactly the same]
