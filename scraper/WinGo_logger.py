from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def perform_login(driver, wait, phone_number, password, max_retries=3):
    retries = 0
    driver.get("https://hgnice.bet/#/login")
    
    time.sleep(5)
    while retries < max_retries:
        try:
            logging.info(f"Attempting login (Attempt {retries + 1}/{max_retries})")
            
            # Wait for login elements
            phone_field = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[1]/div[2]/input')
            ))
            password_field = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="app"]/div[2]/div[4]/div[1]/div/div[2]/div[2]/input')
            ))
            
            # Clear fields and input credentials
            phone_field.clear()
            phone_field.send_keys(phone_number)
            password_field.clear()
            password_field.send_keys(password)
            
            # Click login button
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
                time.sleep(5)  # Wait before retrying
                
    logging.error("Maximum login retries exceeded")
    return False

chrome_options = Options()
#chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--mute-audio")
chrome_options.add_argument("--window-size=1920,1080")
logging.info("Initializing WebDriver...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
#driver = webdriver.Chrome(options=chrome_options)

wait = WebDriverWait(driver, 10) #Maximum wait time 10 seconds for the element

try:
    # In your main code:
    phone_number = "1540046875"      
    password = "strongpassword1"

    logging.info("Starting login process...")
    login_success = perform_login(driver, wait, phone_number, password)

    if not login_success:
        logging.critical("Failed to login after multiple attempts. Exiting.")
        driver.quit()
        sys.exit(1)
        
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
    logging.info("Navigating to target page...")
    driver.get("https://hgnice.bet/#/saasLottery/WinGo?gameCode=WinGo_30S&lottery=WinGo")
    time.sleep(3)
    
    # Mute button click
    logging.info("Clicking mute button...")
    wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[3]/div/div[2]')))
    button = driver.find_element(By.XPATH, '/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[3]/div/div[2]')
    button.click()
    logging.info("Clicked mute button...")
    
    parent_div_xpath = '//*[@id="app"]/div[2]/div[8]/div[2]'
    first_number_xpath_template = parent_div_xpath + '/div[{}]/div[1]'
    second_number_xpath_template = parent_div_xpath + '/div[{}]/div[2]'
    page_number_xpath = '//*[@id="app"]/div[2]/div[8]/div[3]/div[2]'
    next_page_button_xpath = '//*[@id="app"]/div[2]/div[8]/div[3]/div[3]/i'

    last_written_number = None
    last_written_page = 1
    
    # Define base folder for logs
    base_folder = r'D:\Python Projects\RG3\datasets'

    # Create the base folder if it doesn't exist
    os.makedirs(base_folder, exist_ok=True)

    # Get the current date to organize logs by date
    current_date = datetime.now().strftime('%d-%m-%Y')  # e.g., "2024-12-09"

    # Create a subfolder for the current date
    date_folder = os.path.join(base_folder, current_date)
    os.makedirs(date_folder, exist_ok=True)  # Create the date folder if it doesn't exist

    sub_folder_WinGO = os.path.join(date_folder, "WinGo")
    os.makedirs(sub_folder_WinGO, exist_ok=True)
    
    # Create the log file in the date-specific folder
    timestamp = datetime.now().strftime('%H-%M-%S')  # Time-specific suffix for the file
    file_name = os.path.join(sub_folder_WinGO, f'numbers_{timestamp}.txt')

    logging.info("Creating log file...")
    with open(file_name, 'a+') as file:
        current_page = 1
        row_to_start = 1

        # Go to page 2 first and wait for reset to page 1
        logging.info("Navigating to page 2 and waiting for reset to page 1...")
        next_page_button = driver.find_element(By.XPATH, next_page_button_xpath)
        next_page_button.click()  # Go to page 2
        previous_page = 0
        while True:
            try:
                # Wait for the page to reset to page 1
                page_number_text = driver.find_element(By.XPATH, page_number_xpath).text
                current_page = int(page_number_text.split('/')[0])

                if current_page == 1:
                    # Start processing numbers from page 1
                    time.sleep(1)
                    break
                time.sleep(0.5)

            except Exception as e:
                logging.error(f"Error: {e}")
                time.sleep(5)  # Retry after a short delay
                
        previous_page = 0
        last_page = 15 # the last page you want to read
        
        while True:
            current_page = int(page_number_text.split('/')[0])
            if current_page > last_page:
                break
            if(current_page < previous_page):
                break
            logging.info(f"Processing page {current_page}...")
            for row in range(1, 11):
                first_number = driver.find_element(By.XPATH, first_number_xpath_template.format(row)).text
                second_number = driver.find_element(By.XPATH, second_number_xpath_template.format(row)).text
                file.write(f"{first_number}, {second_number}\n")

            # Move to the next page only if we're not on the last page
            if current_page < last_page + 1:
                next_page_button = driver.find_element(By.XPATH, next_page_button_xpath)
                next_page_button.click()

                # Wait until the page number changes
                wait.until(EC.presence_of_element_located((By.XPATH, page_number_xpath)))
                page_number_text = driver.find_element(By.XPATH, page_number_xpath).text
                previous_page = current_page
                current_page = int(page_number_text.split('/')[0])
                time.sleep(1)

    logging.info("Finished processing all pages.")

    
    
except Exception as e:
    logging.error(f"Critical error: {e}")   

finally:
    logging.info("Quitting WebDriver...")
    driver.quit()
    sys.exit()
