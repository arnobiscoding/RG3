import requests
from bs4 import BeautifulSoup
import sys
import json
import os
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# Load environment variables from .env file
load_dotenv()

# Create a session to maintain cookies across requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# Store the mmi parameter after login
mmi_parameter = None

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    print("ERROR: MONGO_URI not found in environment variables. Add it to .env")
    sys.exit(1)

try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')  # Test connection
    db = mongo_client['ucam_bot']
    state_collection = db['bot_state']
    print("✅ Connected to MongoDB Atlas successfully.")
except ServerSelectionTimeoutError as e:
    print("❌ ERROR: Failed to connect to MongoDB Atlas. Check MONGO_URI.")
    print(f"   Details: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERROR: MongoDB connection error: {e}")
    sys.exit(1)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
POLL_INTERVAL_SECONDS = 60  # Poll every 60 seconds

# GitHub Actions timeout: 6 hours (21600 seconds). Exit after 5.5 hours to be safe.
MAX_RUNTIME_SECONDS = 5.5 * 3600
start_time = time.time()

BASE_URL = 'https://ucam.uiu.ac.bd'

# Store credentials for re-login if session expires
USER_ID = os.getenv('USER_ID')
PASSWORD = os.getenv('PASSWORD')
if not USER_ID or not PASSWORD:
    print("ERROR: USER_ID and PASSWORD not found in environment variables.")
    sys.exit(1)

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False

def login_ucam(session, user_id, password, max_retries=3):
    """Attempts to log in to UCAM with retries on failure using HTTP requests."""
    global mmi_parameter
    
    for attempt in range(1, max_retries + 1):
        try:
            # First, get the login page to extract any necessary tokens
            login_url = f'{BASE_URL}/Security/Login.aspx'
            response = session.get(login_url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Parse the page to extract any CSRF tokens or hidden fields
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract form data (looking for hidden fields that might be needed)
            form_data = {}
            for hidden_input in soup.find_all('input', {'type': 'hidden'}):
                name = hidden_input.get('name')
                value = hidden_input.get('value', '')
                if name:
                    form_data[name] = value
            
            # Add credentials
            form_data['ctl00$logMain$UserName'] = user_id
            form_data['ctl00$logMain$Password'] = password
            form_data['ctl00$logMain$Button1'] = 'Sign In'  # Button value
            
            # Submit login form
            response = session.post(login_url, data=form_data, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Try to extract mmi parameter from the response or navigate to course page to get it
            if 'mmi=' in response.text:
                # Extract mmi from the page
                import re
                match = re.search(r'mmi=([a-zA-Z0-9]+)', response.text)
                if match:
                    mmi_parameter = match.group(1)
                    print(f"✅ Extracted mmi parameter: {mmi_parameter}")
            
            # Check if login was successful
            if 'dashboard' in response.text.lower() or 'logout' in response.text.lower() or 'course' in response.text.lower():
                print("✅ Login successful!")
                return True
            else:
                print(f"Login attempt {attempt}: Authentication may have failed")
                if attempt == max_retries:
                    return False
                time.sleep(2)
        except Exception as e:
            print(f"Login attempt {attempt} failed: {e}")
            if attempt == max_retries:
                return False
            time.sleep(2)

def is_session_valid():
    """Check if current session is still valid by attempting a request."""
    try:
        url = f'{BASE_URL}/Student/StudentCourseHistory.aspx'
        if mmi_parameter:
            url += f'?mmi={mmi_parameter}'
        response = session.get(url, timeout=10, allow_redirects=True)
        if response.status_code == 404 or 'login' in response.url.lower():
            return False
        return response.status_code == 200
    except Exception:
        return False

def with_retries(task_fn, max_retries=3, delay=2, *args, **kwargs):
    """Generic retry helper for any task."""
    for attempt in range(1, max_retries + 1):
        try:
            return task_fn(*args, **kwargs)
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                raise
            time.sleep(delay)

def get_table_html(force_fresh=False):
    """Fetch the course history page and extract table HTML."""
    global mmi_parameter
    try:
        # Check if we need to re-login
        if force_fresh or not is_session_valid():
            print("🔄 Session expired or invalid. Re-logging in...")
            if login_ucam(session, USER_ID, PASSWORD):
                print("✅ Re-login successful!")
            else:
                raise Exception("Re-login failed")
        
        # Navigate to the course history page with mmi parameter if available
        url = f'{BASE_URL}/Student/StudentCourseHistory.aspx'
        if mmi_parameter:
            url += f'?mmi={mmi_parameter}'
        
        response = session.get(url, timeout=10, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Failed to fetch course page: {e}")
        raise

def extract_courses(page_html):
    """Parse page HTML and return list of course dicts."""
    soup = BeautifulSoup(page_html, 'lxml')
    # Look for the course table
    table = soup.find('table', {'id': 'ctl00_MainContainer_gvRegisteredCourse'})
    
    if not table:
        raise ValueError("Course table not found on page")
    
    rows = table.find_all('tr')
    from bs4 import Tag
    
    header_row = next((row for row in rows if isinstance(row, Tag) and row.find_all('th')), None)
    if header_row is None:
        raise ValueError("No header row found in table.")
    
    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]
    course_data = []
    
    for row in rows[1:]:
        if isinstance(row, Tag):
            cols = [td.get_text(strip=True) for td in row.find_all('td')]
            if cols:
                course_data.append(dict(zip(headers, cols)))
    
    return course_data

def course_key(course):
    """Return a unique identifier for a course."""
    return (
        course['Course ID'].strip(),
        course['Course Name'].strip(),
        course['Trimester'].strip()
    )

def load_bot_state():
    """Load persistent state from MongoDB. Returns dict with 'running_courses' and 'notified_courses'."""
    try:
        doc = state_collection.find_one({'_id': 'state'})
        if doc:
            return {
                'running_courses': doc.get('running_courses', []),
                'notified_courses': doc.get('notified_courses', [])
            }
    except Exception as e:
        print(f"Failed to load bot state from MongoDB: {e}")
    return {'running_courses': [], 'notified_courses': []}

def save_bot_state(running_courses, notified_courses):
    """Save persistent state to MongoDB."""
    try:
        state_collection.update_one(
            {'_id': 'state'},
            {
                '$set': {
                    'running_courses': running_courses,
                    'notified_courses': notified_courses,
                    'last_updated': (datetime.utcnow() + timedelta(hours=6)).replace(tzinfo=None).isoformat() + '+06:00'
                }
            },
            upsert=True
        )
    except Exception as e:
        print(f"Failed to save bot state to MongoDB: {e}")

def get_message_for_course(course, grade, point):
    """Generate Telegram message based on grade."""
    if grade == "A" and point == 4.00:
        emoji = "🏆🔥"
        tone = "OUTSTANDING ACHIEVEMENT!"
        celebration = "🗿🗿🗿 ABSOLUTE LEGEND! 🗿🗿🗿"
        encouragement = "You're absolutely crushing it! 90-100%! 🚀"
    elif grade == "A-" and point == 3.67:
        emoji = "😔💔"
        tone = "So close to perfection..."
        celebration = "😞 Almost there but not quite... 😞"
        encouragement = "86-89%... You were just a few points away from greatness 😢"
    elif grade == "B+" and point == 3.33:
        emoji = "😰📉"
        tone = "Disappointing Performance"
        celebration = "💔 Could have been better 💔"
        encouragement = "82-85%... This is mediocre at best 😤"
    elif grade == "B" and point == 3.00:
        emoji = "😰🙁"
        tone = "Below Expectations"
        celebration = "😔 This is just average 😔"
        encouragement = "78-81%... Everyone else is probably doing better than this 😢"
    elif grade == "B-" and point == 2.67:
        emoji = "😰😤"
        tone = "Concerning Results"
        celebration = "😰 This is worrying 😰"
        encouragement = "74-77%... Your parents probably expected more 😔"
    elif grade == "C+" and point == 2.33:
        emoji = "😞📉"
        tone = "Poor Performance"
        celebration = "😢 This is barely acceptable 😢"
        encouragement = "70-73%... You're falling behind everyone else 😔"
    elif grade == "C" and point == 2.00:
        emoji = "😭😭"
        tone = "Struggling Hard"
        celebration = "😭 This is embarrassing 😭"
        encouragement = "66-69%... You really need to step up your game 😔"
    elif grade == "C-" and point == 1.67:
        emoji = "🤦‍♂️💩"
        tone = "This is Bad"
        celebration = "😤 What happened here? 😤"
        encouragement = "62-65%... This is really disappointing 😔"
    elif grade == "D+" and point == 1.33:
        emoji = "😰☠️"
        tone = "Terrible Performance"
        celebration = "😤 This is unacceptable 😤"
        encouragement = "58-61%... You barely scraped by 😔"
    elif grade == "D" and point == 1.00:
        emoji = "😵☠️"
        tone = "Rock Bottom"
        celebration = "😵 Barely surviving 😵"
        encouragement = "55-57%... This is the minimum to not fail 😔"
    else:  # F grade
        emoji = "💀⚰️"
        tone = "Complete Failure"
        celebration = "😭😭😭 TOTAL DISASTER 😭😭😭"
        encouragement = "You failed... Time to face the disappointment 😔"

    message = (
        f"{emoji} <b>{celebration}</b>\n\n"
        f"🎊 <b>{tone}</b>\n"
        f"{encouragement}\n\n"
        f"📚 Course: <b>{course['Course Name'].strip()}</b>\n"
        f"🆔 Course ID: <b>{course['Course ID'].strip()}</b>\n"
        f"📅 Trimester: {course['Trimester'].strip()}\n"
        f"💳 Credit: {course['Credit'].strip()}\n"
        f"🏆 Grade: <b>{grade}</b>\n"
        f"📊 Point: <b>{point}</b>\n\n"
        f"🎉 Keep up the amazing work! 🎉"
    )
    return message

# --- Main Execution ---
if not login_ucam(session, USER_ID, PASSWORD):
    mongo_client.close()
    sys.exit(1)

try:
    # Load persistent state from MongoDB
    state = load_bot_state()
    running_courses = state.get('running_courses', [])
    notified_courses = state.get('notified_courses', [])

    # On first run, initialize running_courses from current UCAM data
    if not running_courses:
        print("First run detected. Initializing running courses from UCAM...")
        page_html = with_retries(get_table_html, 3, 2)
        course_data = extract_courses(page_html)
        running_courses = [c for c in course_data if not c.get('Grade', '').strip() and not c.get('Point', '').strip()]
        print(f"Found {len(running_courses)} running courses.")
        save_bot_state(running_courses, notified_courses)

    print(f"\n✅ Bot started. Monitoring {len(running_courses)} courses. Polling every {POLL_INTERVAL_SECONDS} seconds.\n")
    print("📋 Courses being monitored:")
    for i, course in enumerate(running_courses, 1):
        print(f"   {i}. {course['Course Name']} ({course['Course ID']}) - Trimester: {course['Trimester']}")

    # Main polling loop
    while True:
        # Check if we're approaching the 6-hour GitHub Actions timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_RUNTIME_SECONDS:
            print(f"\n⏰ Approaching 6-hour GitHub Actions timeout. Exiting gracefully after {elapsed_time/3600:.1f} hours.")
            save_bot_state(running_courses, notified_courses)
            break
        
        try:
            print(f"\n[{datetime.now()}] Checking for published grades...")
            # Fetch fresh data
            page_html = with_retries(get_table_html, 3, 2)
            course_data = extract_courses(page_html)

            for saved_course in running_courses[:]:  # Iterate over copy to allow removal
                key = course_key(saved_course)
                
                # Find current course data
                current_course = None
                for course in course_data:
                    if course_key(course) == key:
                        current_course = course
                        break
                
                if current_course:
                    grade = current_course.get('Grade', '').strip()
                    point = current_course.get('Point', '').strip()
                    
                    # Check if grade was just published
                    if grade and point and key not in notified_courses:
                        print(f"✅ Result published for: {current_course['Course Name']} - Grade: {grade}, Point: {point}")
                        
                        message = get_message_for_course(current_course, grade, float(point))
                        if with_retries(send_telegram_message, 3, 2, message):
                            notified_courses.append(key)
                            running_courses.remove(saved_course)
                            print(f"✅ Notification sent.")
                            save_bot_state(running_courses, notified_courses)

            print(f"📊 Still monitoring {len(running_courses)} courses | Next check in {POLL_INTERVAL_SECONDS//60} min | {elapsed_time/3600:.1f}h runtime")
            time.sleep(POLL_INTERVAL_SECONDS)

        except Exception as e:
            print(f"Error during poll: {e}")
            time.sleep(60)  # Wait a minute before retrying on error

except Exception as e:
    print(f"Fatal error: {e}")
finally:
    mongo_client.close()
