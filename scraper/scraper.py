import logging
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load local .env file
load_dotenv()

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
        except ServerSelectionTimeoutError as e:
            logging.error(f"❌ ERROR: Failed to connect to MongoDB. Attempt {attempt}")
            if attempt == 3: wingo_collection = None
            time.sleep(2)
else:
    logging.critical("❌ ERROR: MONGO_URI not found in .env file.")

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

    if not PHONE_NUMBER or not PASSWORD or wingo_collection is None:
        logging.critical("ERROR: Missing credentials or MongoDB connection.")
        return

    chrome_options = Options()
    # COMMENT OUT the next line if you want to see the browser window locally
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    driver = None
    try:
        logging.info("Initializing local WebDriver...")
        # Local setup uses ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 15)

        if not perform_login(driver, wait, PHONE_NUMBER, PASSWORD):
            return

        # --- Handle Popups Resiliently ---
        popup_xpaths = [
            "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]",
            "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]",
            "/html/body/div[1]/div[6]/div[2]/div[2]"
        ]
        for xpath in popup_xpaths:
            try:
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                btn.click()
                time.sleep(1)
            except:
                logging.info(f"Popup {xpath} not found/clickable, skipping.")

        # Navigate to WinGo
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]"))).click()
        time.sleep(2)

        # Wait for timer sync
        time_xpath = '/html/body/div[1]/div[2]/div[2]/div[6]'
        while True:
            time_str = ''.join([d.text for d in driver.find_elements(By.XPATH, time_xpath + '/div')])
            if time_str == "00:00": break
            time.sleep(0.5)
        time.sleep(2)

        # Scraping Logic
        all_records = []
        for current_page in range(1, 16):
            wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div[4]/div[2]/div/div[2]')))
            rows = driver.find_elements(By.XPATH, '/html/body/div[1]/div[2]/div[4]/div[2]/div/div[2]/div[contains(@class, "van-row")]')
            
            for row in rows:
                try:
                    p = row.find_element(By.XPATH, './div[1]').text
                    n = row.find_element(By.XPATH, './/div[contains(@class, "numcenter")]/div').text
                    all_records.append({
                        '_id': p, # Use period as unique ID
                        'period': p,
                        'number': n,
                        'color': COLOR_MAP.get(n, 'unknown'),
                        'scraped_at': datetime.now(timezone.utc)
                    })
                except: continue

            if current_page < 15:
                next_btn = driver.find_element(By.XPATH, '//div[contains(@class, "record-foot-next")]')
                next_btn.click()
                time.sleep(1.5)

        # Upsert to MongoDB
        count = 0
        for record in all_records:
            result = wingo_collection.update_one({'_id': record['_id']}, {'$set': record}, upsert=True)
            if result.upserted_id: count += 1
        
        logging.info(f"✅ Task Finished. Added {count} new records.")

    except Exception as e:
        logging.error(f"❌ Scraper Task Failed: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    while True:
        # Check connection again in case it dropped
        if wingo_collection is not None:
            run_scraper_task()
            logging.info("💤 Sleeping for 30 minutes...")
        else:
            logging.error("❌ MongoDB not connected. Retrying connection...")
            # Attempt to reconnect logic could go here
        
        time.sleep(1800)