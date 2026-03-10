import logging
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Load local .env file
load_dotenv()

def configure_logging():
    log_dir = Path(__file__).resolve().parent / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    today_name = f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log"
    log_file = log_dir / today_name

    # Keep only today's log file.
    for existing in log_dir.glob("scraper_*.log"):
        if existing.name != today_name:
            try:
                existing.unlink()
            except OSError:
                pass

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


configure_logging()

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
        except ServerSelectionTimeoutError:
            logging.error(f"❌ ERROR: Failed to connect to MongoDB. Attempt {attempt}")
            if attempt == 3:
                wingo_collection = None
            time.sleep(2)
else:
    logging.critical("❌ ERROR: MONGO_URI not found in .env file.")


COLOR_MAP = {
    '0': 'red/violet', '1': 'green', '2': 'red', '3': 'green', '4': 'red',
    '5': 'green/violet', '6': 'red', '7': 'green', '8': 'red', '9': 'green'
}

UTC_PLUS_6 = timezone(timedelta(hours=6))


def get_valid_period_prefix(records):
    if len(records) < 2:
        return records

    for index in range(len(records) - 1):
        current_period = records[index]['period']
        next_period = records[index + 1]['period']

        try:
            current_last4 = int(current_period[-4:])
            next_last4 = int(next_period[-4:])
        except ValueError:
            logging.error(f"Invalid period format at index {index}: {current_period} -> {next_period}")
            return records[:index + 1]

        difference = current_last4 - next_last4
        if difference not in (1, 2879, -2879):
            logging.error(
                "Period validation failed at index %s: %s -> %s (last4 diff=%s)",
                index,
                current_period,
                next_period,
                difference,
            )
            return records[:index + 1]

    return records


def drop_duplicate_periods(records):
    if not records:
        return records

    deduped_records = []
    seen_periods = set()
    duplicate_count = 0

    for record in records:
        period = record.get('period')
        if not period:
            continue

        if period in seen_periods:
            duplicate_count += 1
            continue

        seen_periods.add(period)
        deduped_records.append(record)

    if duplicate_count:
        logging.warning(
            "Dropped %s duplicate period rows before validation.",
            duplicate_count,
        )

    return deduped_records


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


def close_popups(wait):
    popup_xpaths = [
        "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]",
        "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]",
        "/html/body/div[1]/div[6]/div[2]/div[2]"
    ]

    logging.info("Checking and closing popups...")
    for xpath in popup_xpaths:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            btn.click()
            time.sleep(1)
        except Exception:
            logging.info(f"Popup {xpath} not found/clickable, skipping.")


def go_to_wingo_page(wait):
    logging.info("Navigating to WinGo page...")
    wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]"))).click()
    time.sleep(3)
    logging.info("Reached WinGo page.")


def wait_for_clock_and_read_rows(driver, wait, total_pages=15):
    logging.info("Waiting for clock sync (00:00)...")
    time_xpath = '/html/body/div[1]/div[2]/div[2]/div[6]'
    while True:
        time_str = ''.join([d.text for d in driver.find_elements(By.XPATH, time_xpath + '/div')])
        if time_str == "00:00":
            break
        time.sleep(0.5)
    time.sleep(2)
    logging.info("Clock synced. Starting row reads.")

    all_records = []
    parent_xpath = '/html/body/div[1]/div[2]/div[4]/div[2]/div/div[2]'
    previous_page_first_period = None

    def get_first_visible_period():
        first_period_nodes = driver.find_elements(By.XPATH, f'{parent_xpath}/div[1]/div[1]')
        if not first_period_nodes:
            return ""
        return first_period_nodes[0].text.strip()

    def read_current_page_records():
        records = []
        wait.until(EC.presence_of_element_located((By.XPATH, parent_xpath)))
        row_count = len(driver.find_elements(By.XPATH, f'{parent_xpath}/div'))

        for row_index in range(1, row_count + 1):
            try:
                period_xpath = f'{parent_xpath}/div[{row_index}]/div[1]'
                number_xpath = f'{parent_xpath}/div[{row_index}]/div[2]/div'
                period = driver.find_element(By.XPATH, period_xpath).text
                number = driver.find_element(By.XPATH, number_xpath).text
                records.append({
                    '_id': period,
                    'period': period,
                    'number': number,
                    'color': COLOR_MAP.get(number, 'unknown'),
                    'scraped_at': datetime.now(UTC_PLUS_6).isoformat(timespec='milliseconds')
                })
            except Exception:
                continue

        return records

    for current_page in range(1, total_pages + 1):
        logging.info(f"Reading page {current_page}/{total_pages}...")
        time.sleep(1)

        page_records = []
        for attempt in range(1, 4):
            candidate_records = read_current_page_records()
            if not candidate_records:
                logging.warning(
                    "No rows found on page %s (attempt %s/3). Retrying...",
                    current_page,
                    attempt,
                )
                time.sleep(0.6)
                continue

            current_first_period = candidate_records[0]['period']
            if previous_page_first_period and current_first_period == previous_page_first_period:
                logging.warning(
                    "Page %s appears unchanged after navigation (attempt %s/3). Retrying read...",
                    current_page,
                    attempt,
                )
                time.sleep(0.8)
                continue

            page_records = candidate_records
            break

        if not page_records:
            page_records = read_current_page_records()
            if page_records and previous_page_first_period and page_records[0]['period'] == previous_page_first_period:
                logging.warning(
                    "Page %s still appears unchanged after retries; continuing with captured rows.",
                    current_page,
                )

        all_records.extend(page_records)
        if page_records:
            previous_page_first_period = page_records[0]['period']

        if current_page < total_pages:
            next_btn = driver.find_element(By.XPATH, '//div[contains(@class, "record-foot-next")]')
            next_btn.click()
            if previous_page_first_period:
                try:
                    WebDriverWait(driver, 6).until(
                        lambda _driver: (
                            (new_first := get_first_visible_period())
                            and new_first != previous_page_first_period
                        )
                    )
                except Exception:
                    logging.warning(
                        "Timed out waiting for page %s -> %s transition; continuing with retry logic.",
                        current_page,
                        current_page + 1,
                    )

    logging.info(f"Finished reading pages. Collected {len(all_records)} total rows.")

    return all_records


def upsert_records_to_mongo(records):
    logging.info(f"Uploading {len(records)} records to MongoDB...")
    count = 0
    for record in records:
        result = wingo_collection.update_one({'_id': record['_id']}, {'$set': record}, upsert=True)
        if result.upserted_id:
            count += 1

    logging.info(f"✅ Task Finished. Added {count} new records.")


def run_scraper_task():
    phone_number = os.environ.get('PHONE_NUMBER')
    password = os.environ.get('PASSWORD')

    if not phone_number or not password or wingo_collection is None:
        logging.critical("ERROR: Missing credentials or MongoDB connection.")
        return

    chrome_options = Options()

    # COMMENT OUT the next line if you want to see the browser window locally
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    driver = None

    try:
        logging.info("Initializing local WebDriver...")
        service = Service(ChromeDriverManager().install(), log_output=subprocess.DEVNULL)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 15)

        if not perform_login(driver, wait, phone_number, password):
            return

        close_popups(wait)
        go_to_wingo_page(wait)
        all_records = wait_for_clock_and_read_rows(driver, wait, total_pages=15)

        all_records = drop_duplicate_periods(all_records)

        logging.info("Validating period sequence...")
        valid_records = get_valid_period_prefix(all_records)
        if not valid_records:
            logging.error("Validation failed at the start. Mongo upload was skipped.")
            return

        if len(valid_records) < len(all_records):
            logging.warning(
                "Validation failed mid-sequence. Uploading only valid prefix: %s/%s records.",
                len(valid_records),
                len(all_records),
            )
        else:
            logging.info("Validation passed for all collected records.")

        upsert_records_to_mongo(valid_records)
    except Exception as e:
        logging.error(f"❌ Scraper Task Failed: {e}")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    logging.info("=" * 72)
    logging.info("Run started")
    try:
        if wingo_collection is not None:
            run_scraper_task()
        else:
            logging.error("Run skipped: MongoDB connection is not available.")
    finally:
        logging.info("Run finished")
        logging.info("=" * 72)
