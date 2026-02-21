from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
#chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--mute-audio")
chrome_options.add_argument("--window-size=1920,1080")
# Suppress Google API and Chrome error messages
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--disable-logging")
chrome_options.add_argument("--disable-features=NetworkService,NetworkServiceInProcess")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-default-apps")
chrome_options.add_argument("--disable-popup-blocking")
chrome_options.add_argument("--disable-infobars")
# Make Selenium less detectable
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
# Set a common user-agent
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
logging.info("Initializing WebDriver...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
# Remove navigator.webdriver property
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
    print("Clicking through popups 1...")
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]").click()
    time.sleep(1)
    print("Clicking through popups 2...")
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[11]/div[1]/div[3]").click()
    time.sleep(1)
    print("Clicking through popups 3...")
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[6]/div[2]/div[2]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[6]/div[2]/div[2]").click()
    time.sleep(1)
    # Navigate to target page /html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]
    print("Clicking Wingo Button...")
    wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]")))
    driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div[5]/div[2]/div/div[1]").click()
    time.sleep(1)
    # Click mute button
    logging.info("Clicking mute button...")
    wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[3]/div/div[2]')))
    button = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[3]/div/div[2]')
    button.click()
    logging.info("Clicked mute button...")

    # Combine time and record parsing: only print new records when timer hits 00:00
    record_body_xpath = '/html/body/div[1]/div[2]/div[4]/div[2]/div/div[2]'
    time_xpath = '/html/body/div[1]/div[2]/div[2]/div[6]'
    last_top_period = None
    last_time = None
    logging.info("Starting combined time/record parsing loop...")
    # Add quit flag and input thread
    quit_flag = {'quit': False}
    def check_quit():
        while True:
            user_input = input("Press 'q' and Enter to quit...\n")
            if user_input.strip().lower() == 'q':
                quit_flag['quit'] = True
                break

    input_thread = threading.Thread(target=check_quit, daemon=True)
    input_thread.start()

    last_top_period = None
    first_run = True
    try:
        while not quit_flag['quit']:
            # Wait for timer to hit 00:00
            wait.until(EC.presence_of_element_located((By.XPATH, time_xpath)))
            time_div = driver.find_element(By.XPATH, time_xpath)
            child_divs = time_div.find_elements(By.XPATH, './div')
            time_str = ''.join([div.text for div in child_divs])
            if time_str == "00:00":
                time.sleep(1)  # Wait for record list to update
                wait.until(EC.presence_of_element_located((By.XPATH, record_body_xpath)))
                record_body = driver.find_element(By.XPATH, record_body_xpath)
                rows = record_body.find_elements(By.XPATH, './div[contains(@class, "van-row")]')
                records = []
                for row in rows:
                    try:
                        period = row.find_element(By.XPATH, './div[contains(@class, "van-col--10")]').text
                        number = row.find_element(By.XPATH, './div[contains(@class, "numcenter")]/div').text
                        big_small = row.find_element(By.XPATH, './div[contains(@class, "van-col--5")][2]/span').text
                        # Color: get class from record-body-num or record-origin-I
                        num_div = row.find_element(By.XPATH, './div[contains(@class, "numcenter")]/div')
                        color_class = num_div.get_attribute('class')
                        color = None
                        if 'defaultColor' in color_class:
                            color = 'default'
                        elif 'greenColor' in color_class:
                            color = 'green'
                        elif 'mixedColor0' in color_class:
                            color = 'mixed0'
                        else:
                            # Try to get color from record-origin-I
                            try:
                                color_div = row.find_element(By.XPATH, './/div[contains(@class, "record-origin-I")]')
                                color_class2 = color_div.get_attribute('class')
                                if 'red' in color_class2:
                                    color = 'red'
                                elif 'green' in color_class2:
                                    color = 'green'
                                elif 'violet' in color_class2:
                                    color = 'violet'
                            except:
                                color = 'unknown'
                        records.append((period, number, big_small, color))
                    except Exception as e:
                        logging.error(f"Error parsing row: {e}")
                records = records[::-1]
                # On first run, print all records
                if first_run:
                    print("\nCurrent 10 records (oldest to newest):")
                    for rec in records:
                        print(f"Period: {rec[0]}, Number: {rec[1]}, Big/Small: {rec[2]}, Color: {rec[3]}")
                    first_run = False
                    last_top_period = records[-1][0] if records else None
                else:
                    # Only print new row if top period changed
                    if records and records[-1][0] != last_top_period:
                        new_row = records[-1]
                        # Color logic based on number
                        num_val = new_row[1]
                        color_map = {
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
                        color = color_map.get(num_val, 'unknown')
                        print(f"Period: {new_row[0]}, Number: {new_row[1]}, Big/Small: {new_row[2]}, Color: {color}")
                        last_top_period = records[-1][0]
                # Wait for timer to move off 00:00 before next check
                while True:
                    wait.until(EC.presence_of_element_located((By.XPATH, time_xpath)))
                    time_div = driver.find_element(By.XPATH, time_xpath)
                    child_divs = time_div.find_elements(By.XPATH, './div')
                    next_time_str = ''.join([div.text for div in child_divs])
                    if next_time_str != "00:00":
                        break
                    time.sleep(0.2)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:
        logging.error(f"Error in combined parsing loop: {e}")
finally:
    driver.quit()
