import logging
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from datetime import datetime, timezone

# Optional for local testing; Heroku will ignore this if the file isn't pushed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- MongoDB Connection Pooling ---
MONGO_URI = os.environ.get('MONGO_URI')
mongo_client = None
wingo_collection = None

if MONGO_URI:
    for attempt in range(1, 4):
        try:
            mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command('ping')
            db = mongo_client['Restless_Gambler']
            wingo_collection = db['Wingo_Dataset']
            logging.info("✅ Connected to MongoDB successfully.")
            break
        except Exception as e:
            logging.error(f"❌ MongoDB connection attempt {attempt} failed: {e}")
            if attempt == 3: wingo_collection = None
            time.sleep(2)
else:
    logging.critical("❌ ERROR: MONGO_URI not found.")

COLOR_MAP = {
    '0': 'red/violet', '1': 'green', '2': 'red', '3': 'green', '4': 'red',
    '5': 'green/violet', '6': 'red', '7': 'green', '8': 'red', '9': 'green'
}

def perform_login(driver, wait, phone_number, password, max_retries=3):
    retries = 0
    driver.get("https://hgnice.bet/#/login")
    time.sleep(5)
    while retries < max_retries:
        try:
            logging.info(f"Attempting login (Attempt {retries + 1}/{max_retries})")
            phone_field = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[1]/div[2]/input')))
            password_field = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[2]/div[2]/input')))
            
            phone_field.clear()
            phone_field.send_keys(phone_number)
            password_field.clear()
            password_field.send_keys(password)
            
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[4]/button[1]')))
            login_button.click()
            logging.info("Login successful")
            return True
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            retries += 1
            driver.refresh()
            time.sleep(5)
    return False

def run_scraper_task():
    PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
    PASSWORD = os.environ.get('PASSWORD')
    GOOGLE_CHROME_BIN = os.environ.get('GOOGLE_CHROME_BIN')
    CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH')

    if not PHONE_NUMBER or not PASSWORD or wingo_collection is None:
        logging.critical("ERROR: Credentials or MongoDB collection unavailable.")
        return

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    if GOOGLE_CHROME_BIN:
        chrome_options.binary_location = GOOGLE_CHROME_BIN

    driver = None
    try:
        logging.info("Initializing WebDriver...")
        service = Service(executable_path=CHROMEDRIVER_PATH) if CHROMEDRIVER_PATH else Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })
        wait = WebDriverWait(driver, 20) # Increased timeout for Heroku latency

        if not perform_login(driver, wait, PHONE_NUMBER, PASSWORD):
            return

        # Improved Popup Handling using a loop
        popup_xpath = "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]"
        for i in range(3):
            try:
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, popup_xpath)))
                driver.execute_script("arguments[0].click();", btn) # JS Click is more reliable
                logging.info(f"Dismissed popup {i+1}")
                time.sleep(1)
            except: break

        # Navigate to target
        target_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]")))
        driver.execute_script("arguments[0].click();", target_btn)
        time.sleep(2)

        # Timer Sync
        time_xpath = '/html/body/div[1]/div[2]/div[2]/div[6]'
        logging.info("Waiting for timer to sync...")
        while True:
            try:
                time_str = ''.join([d.text for d in driver.find_elements(By.XPATH, time_xpath + '/div')])
                if time_str == "00:00": break
            except: pass
            time.sleep(0.5)
        
        logging.info("Timer hit 00:00. Waiting 5s for table to refresh...")
        time.sleep(5) # Crucial: Wait for the site to process the result

        # Scrape Pages
        all_records = []
        for current_page in range(1, 16):
            # 1. Wait until at least one data row is VISIBLE
            try:
                wait.until(EC.visibility_of_element_located((By.XPATH, '//div[contains(@class, "van-row")]//div[contains(@class, "numcenter")]')))
            except:
                logging.warning(f"Timeout waiting for rows on page {current_page}")
                break

            # 2. Get rows
            rows = driver.find_elements(By.XPATH, '//div[contains(@class, "van-row") and .//div[contains(@class, "numcenter")]]')
            
            for row in rows:
                try:
                    # Use relative XPaths for safety
                    p = row.find_element(By.XPATH, './div[1]').text
                    n = row.find_element(By.XPATH, './/div[contains(@class, "numcenter")]/div').text
                    bs = row.find_element(By.XPATH, './div[contains(@class, "van-col--5")][2]/span').text
                    
                    if p and n: # Ensure we didn't get empty strings
                        all_records.append({
                            '_id': p,
                            'period': p,
                            'number': n,
                            'big_small': bs,
                            'color': COLOR_MAP.get(n, 'unknown'),
                            'scraped_at': datetime.now(timezone.utc)
                        })
                except: continue
            
            # Navigate to next page
            if current_page < 15:
                try:
                    next_btn = driver.find_element(By.XPATH, '//div[contains(@class, "record-foot-next")]')
                    driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(2) # Wait for page transition
                except: 
                    logging.warning(f"Could not find next button on page {current_page}")
                    break

        # Upsert
        if all_records:
            success_count = 0
            for record in all_records:
                try:
                    wingo_collection.update_one({'_id': record['_id']}, {'$set': record}, upsert=True)
                    success_count += 1
                except: pass
            logging.info(f"✅ Scrape successful. Processed {success_count} unique periods.")
        else:
            logging.error("❌ Failed to find any records. Check site accessibility.")

    except Exception as e:
        logging.critical(f"❌ Scraper task failed: {e}")
    finally:
        if driver:
            driver.close()
            driver.quit()

if __name__ == "__main__":
    while True:
        run_scraper_task()
        logging.info("💤 Sleeping for 30 minutes...")
        time.sleep(1800)