import logging
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Load local .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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


def write_records_to_txt(records):
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"wingo_data_{timestamp}.txt")

    logging.info(f"Writing {len(records)} records to TXT file...")

    with open(output_file, "w", encoding="utf-8") as file:
        file.write("period,number,color,scraped_at\n")
        for record in records:
            file.write(
                f"{record['period']},{record['number']},{record['color']},{record['scraped_at']}\n"
            )

    logging.info(f"✅ Task Finished. Saved {len(records)} records to {output_file}")


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

    for current_page in range(1, total_pages + 1):
        logging.info(f"Reading page {current_page}/{total_pages}...")
        time.sleep(1)
        wait.until(EC.presence_of_element_located((By.XPATH, parent_xpath)))
        row_count = len(driver.find_elements(By.XPATH, f'{parent_xpath}/div'))

        for row_index in range(1, row_count + 1):
            try:
                period_xpath = f'{parent_xpath}/div[{row_index}]/div[1]'
                number_xpath = f'{parent_xpath}/div[{row_index}]/div[2]/div'
                period = driver.find_element(By.XPATH, period_xpath).text
                number = driver.find_element(By.XPATH, number_xpath).text
                all_records.append({
                    'period': period,
                    'number': number,
                    'color': COLOR_MAP.get(number, 'unknown'),
                    'scraped_at': datetime.now(UTC_PLUS_6).isoformat()
                })
            except Exception:
                continue

        if current_page < total_pages:
            next_btn = driver.find_element(By.XPATH, '//div[contains(@class, "record-foot-next")]')
            next_btn.click()

    logging.info(f"Finished reading pages. Collected {len(all_records)} total rows.")

    return all_records


def run_scraper_task():
    phone_number = os.environ.get('PHONE_NUMBER')
    password = os.environ.get('PASSWORD')

    if not phone_number or not password:
        logging.critical("ERROR: Missing PHONE_NUMBER or PASSWORD in .env file.")
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

        valid_records = get_valid_period_prefix(all_records)
        logging.info("Validating period sequence...")
        if not valid_records:
            logging.error("Validation failed at the start. TXT file was not created.")
            return

        if len(valid_records) < len(all_records):
            logging.warning(
                "Validation failed mid-sequence. Writing only valid prefix: %s/%s records.",
                len(valid_records),
                len(all_records),
            )
        else:
            logging.info("Validation passed for all collected records.")

        write_records_to_txt(valid_records)
    except Exception as e:
        logging.error(f"❌ Scraper Task Failed: {e}")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    run_scraper_task()
