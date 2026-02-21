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

# Only for local testing; Heroku uses Dashboard Config Vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- MongoDB Connection Setup ---
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
            logging.error(f"❌ MongoDB attempt {attempt} failed: {e}")
            if attempt == 3: wingo_collection = None
            time.sleep(2)
else:
    logging.critical("❌ ERROR: MONGO_URI not found.")

COLOR_MAP = {
    '0': 'red/violet', '1': 'green', '2': 'red', '3': 'green', '4': 'red',
    '5': 'green/violet', '6': 'red', '7': 'green', '8': 'red', '9': 'green'
}

def js_click(driver, element):
    """Fallback click method for Heroku's headless mode"""
    driver.execute_script("arguments[0].click();", element)

def perform_login(driver, wait, phone_number, password, max_retries=3):
    retries = 0
    driver.get("https://hgnice.bet/#/login")
    time.sleep(5)
    while retries < max_retries:
        try:
            logging.info(f"Attempting login (Attempt {retries + 1}/{max_retries})")
            phone_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'phone')]")))
            password_field = driver.find_element(By.XPATH, "//input[@type='password']")
            
            phone_field.clear()
            phone_field.send_keys(phone_number)
            password_field.clear()
            password_field.send_keys(password)
            
            login_button = wait.until(EC.element_to_be_clickable((By.TAG_NAME, "button")))
            js_click(driver, login_button)
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

    # Explicit None check for Heroku compatibility
    if not PHONE_NUMBER or not PASSWORD or wingo_collection is None:
        logging.critical("ERROR: Missing credentials or MongoDB connection.")
        return

    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    if GOOGLE_CHROME_BIN:
        chrome_options.binary_location = GOOGLE_CHROME_BIN

    driver = None
    try:
        logging.info("Initializing WebDriver...")
        service = Service(executable_path=CHROMEDRIVER_PATH) if CHROMEDRIVER_PATH else Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 20) # Increased timeout for Heroku

        if not perform_login(driver, wait, PHONE_NUMBER, PASSWORD):
            return

        # --- Popup Cleaning (Mandatory for Headless) ---
        time.sleep(5)
        driver.execute_script("""
            var overlays = document.querySelectorAll('.van-overlay, .van-popup, .notice-box');
            overlays.forEach(el => el.remove());
        """)

        # Navigate to WinGo
        nav_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Win Go') or contains(text(), 'WinGo')]")))
        js_click(driver, nav_btn)
        time.sleep(3)

        # Wait for timer sync (00:00)
        time_xpath = '/html/body/div[1]/div[2]/div[2]/div[6]'
        logging.info("Waiting for timer to hit 00:00...")
        while True:
            try:
                time_divs = driver.find_elements(By.XPATH, time_xpath + '/div')
                time_str = ''.join([d.text for d in time_divs])
                if time_str == "00:00": break
            except: pass
            time.sleep(0.5)
        
        logging.info("Timer synced. Waiting 5s for table refresh...")
        time.sleep(5)

        # Scraping Logic
        all_records = []
        for current_page in range(1, 16):
            # Wait for rows to be VISIBLE, not just present
            try:
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".van-row")))
            except:
                logging.warning(f"Rows not visible on page {current_page}. Skipping.")
                break

            rows = driver.find_elements(By.CSS_SELECTOR, ".van-row")
            for row in rows:
                try:
                    data = row.text.split('\n')
                    # Data validation: Ensure the first item looks like a Period ID
                    if len(data) >= 2 and data[0].startswith("202"):
                        p_id = data[0].strip()
                        num = data[1].strip()
                        all_records.append({
                            '_id': p_id,
                            'period': p_id,
                            'number': num,
                            'color': COLOR_MAP.get(num, 'unknown'),
                            'scraped_at': datetime.now(timezone.utc)
                        })
                except: continue

            if current_page < 15:
                try:
                    next_btn = driver.find_element(By.XPATH, "//div[contains(@class, 'next')] | //*[contains(text(), '>')]")
                    js_click(driver, next_btn)
                    time.sleep(2)
                except: break

        # Upsert to MongoDB
        if all_records:
            count = 0
            for record in all_records:
                result = wingo_collection.update_one({'_id': record['_id']}, {'$set': record}, upsert=True)
                if result.upserted_id or result.modified_count: count += 1
            logging.info(f"✅ Task Finished. Processed {count} unique records.")
        else:
            logging.error("❌ No records found during scrape.")

    except Exception as e:
        logging.error(f"❌ Scraper Task Failed: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    while True:
        if wingo_collection is not None:
            run_scraper_task()
        logging.info("💤 Sleeping for 30 minutes...")
        time.sleep(1800)