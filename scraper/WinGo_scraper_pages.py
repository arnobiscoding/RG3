from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Color mapping based on number
COLOR_MAP = {
    '0': 'red/violet',
    '1': 'green',
    '2': 'red',
    '3': 'green',
    '4': 'red',
    '5': 'green/violet',
    '6': 'red',
    '7': 'green',
    '8': 'red',
    '9': 'green'
}

def perform_login(driver, wait, phone_number, password, max_retries=3):
    retries = 0
    driver.get("https://hgnice.bet/#/login")
    time.sleep(5)
    while retries < max_retries:
        try:
            logging.info(f"Attempting login (Attempt {retries + 1}/{max_retries})")
            phone_field = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[1]/div[2]/input')
            ))
            password_field = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[2]/div[2]/input')
            ))
            phone_field.clear()
            phone_field.send_keys(phone_number)
            password_field.clear()
            password_field.send_keys(password)
            login_button = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[4]/button[1]')
            ))
            login_button.click()
            logging.info("Login successful")
            return True
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            retries += 1
            if retries < max_retries:
                logging.info("Refreshing browser for retry...")
                driver.refresh()
                time.sleep(5)
    logging.error("Maximum login retries exceeded")
    return False

chrome_options = Options()
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--mute-audio")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--disable-logging")
chrome_options.add_argument("--disable-features=NetworkService,NetworkServiceInProcess")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-default-apps")
chrome_options.add_argument("--disable-popup-blocking")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
logging.info("Initializing WebDriver...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
    'source': '''
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
    '''
})
wait = WebDriverWait(driver, 10)

try:
    phone_number = "1540046875"
    password = "strongpassword1"
    logging.info("Starting login process...")
    login_success = perform_login(driver, wait, phone_number, password)
    if not login_success:
        logging.critical("Failed to login after multiple attempts. Exiting.")
        driver.quit()
        exit(1)
    # Click through popups
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]").click()
    time.sleep(1)
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]").click()
    time.sleep(1)
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[6]/div[2]/div[2]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[6]/div[2]/div[2]").click()
    time.sleep(1)
    # Navigate to target page
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]").click()
    time.sleep(1)
    # Click mute button
    wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[3]/div/div[2]')))
    button = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[3]/div/div[2]')
    button.click()
    time.sleep(1)

    # Wait for timer to hit 00:00
    time_xpath = '/html/body/div[1]/div[2]/div[2]/div[6]'
    while True:
        wait.until(EC.presence_of_element_located((By.XPATH, time_xpath)))
        time_div = driver.find_element(By.XPATH, time_xpath)
        child_divs = time_div.find_elements(By.XPATH, './div')
        time_str = ''.join([div.text for div in child_divs])
        if time_str == "00:00":
            break
        time.sleep(0.2)
    time.sleep(1)  # Wait for record list to update

    # Parse records for pages 1 to 15 using page number from footer
    record_body_xpath = '/html/body/div[1]/div[2]/div[4]/div[2]/div/div[2]'
    record_footer_xpath = '/html/body/div[1]/div[2]/div[4]/div[2]/div/div[3]'
    page_num_xpath = './div[contains(@class, "record-foot-page")]'
    all_records = []
    current_page = 1
    while current_page <= 15:
        wait.until(EC.presence_of_element_located((By.XPATH, record_body_xpath)))
        record_body = driver.find_element(By.XPATH, record_body_xpath)
        rows = record_body.find_elements(By.XPATH, './div[contains(@class, "van-row")]')
        for row in rows:
            try:
                period = row.find_element(By.XPATH, './div[contains(@class, "van-col--10")]').text
                number = row.find_element(By.XPATH, './div[contains(@class, "numcenter")]/div').text
                big_small = row.find_element(By.XPATH, './div[contains(@class, "van-col--5")][2]/span').text
                color = COLOR_MAP.get(number, 'unknown')
                all_records.append((period, number, big_small, color))
            except Exception as e:
                logging.error(f"Error parsing row: {e}")
        # Go to next page unless last page
        if current_page < 15:
            wait.until(EC.presence_of_element_located((By.XPATH, record_footer_xpath)))
            footer = driver.find_element(By.XPATH, record_footer_xpath)
            page_num_div = footer.find_element(By.XPATH, page_num_xpath)
            page_text = page_num_div.text
            # Click next page
            next_btn = footer.find_element(By.XPATH, './div[contains(@class, "record-foot-next")]')
            next_btn.click()
            time.sleep(1)  # Wait for page to update
            # Wait for page number to update
            while True:
                page_num_div = footer.find_element(By.XPATH, page_num_xpath)
                new_page_text = page_num_div.text
                if new_page_text != page_text:
                    break
                time.sleep(0.2)
        current_page += 1

    # Print all records oldest to newest
    all_records = all_records[::-1]
    print("\nAll records (oldest to newest):")
    for rec in all_records:
        print(f"Period: {rec[0]}, Number: {rec[1]}, Big/Small: {rec[2]}, Color: {rec[3]}")
finally:
    driver.quit()
