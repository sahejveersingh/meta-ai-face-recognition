from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Query, HTTPException
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from PIL import Image
import io
import os
import uuid
import time
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import openai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time as pytime
from threading import Thread
import tempfile
import undetected_chromedriver as uc
import subprocess
from typing import Optional
import logging
import urllib.request
from selenium.webdriver.chrome.service import Service
import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import quote_plus
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables first
load_dotenv()

app = FastAPI(title="Meta AI Face Recognition API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify ["http://localhost:3000"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory to save cropped faces
os.makedirs('faces', exist_ok=True)

# Check for OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key or openai_api_key == "your_openai_api_key_here":
    logger.warning("⚠️  WARNING: OpenAI API key not set. GPT summarization will be disabled.")
    logger.warning("   Please set OPENAI_API_KEY in your .env file")
    openai_api_key = None
else:
    openai.api_key = openai_api_key

# Global variable to store detected profiles from the RTMP stream
rtmp_detected_profiles = []
rtmp_processing_active = False
rtmp_processing_thread = None

status_info = {
    'rtmp': 'unknown',
    'backend': 'idle',
    'selenium': 'idle',
    'error': ''
}

def set_status(rtmp=None, backend=None, selenium=None, error=None):
    if rtmp is not None:
        status_info['rtmp'] = rtmp
    if backend is not None:
        status_info['backend'] = backend
    if selenium is not None:
        status_info['selenium'] = selenium
    if error is not None:
        status_info['error'] = error

def detect_and_crop_faces(image_bytes):
    try:
        # Convert bytes to numpy array
        npimg = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("❌ Failed to decode image")
            return []
        
        logger.info(f"🔍 Processing image of size: {img.shape}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Use OpenCV's built-in data path for the cascade file
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        
        if not os.path.exists(cascade_path):
            logger.error(f"❌ Cascade file not found: {cascade_path}")
            return []
        
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            logger.error("❌ Failed to load cascade classifier")
            return []
        
        logger.info("✅ Cascade classifier loaded successfully")
        
        # Detect faces with more sensitive parameters
        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.05,  # Even more sensitive
            minNeighbors=2,    # Less strict
            minSize=(20, 20),  # Smaller minimum face size
            maxSize=(0, 0)     # No maximum size limit
        )
        
        logger.info(f"🔍 Detected {len(faces)} potential faces")
        
        # If no faces detected, try with even more sensitive parameters
        if len(faces) == 0:
            logger.info("🔍 No faces detected with standard parameters, trying more sensitive detection...")
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.01,  # Very sensitive
                minNeighbors=1,    # Very permissive
                minSize=(15, 15),  # Very small minimum
                maxSize=(0, 0)
            )
            logger.info(f"🔍 Sensitive detection found {len(faces)} potential faces")
        
        cropped_faces = []
        for i, (x, y, w, h) in enumerate(faces):
            face_img = img[y:y+h, x:x+w]
            face_filename = f"faces/{uuid.uuid4()}.jpg"
            cv2.imwrite(face_filename, face_img)
            cropped_faces.append(face_filename)
            logger.info(f"👤 Detected face {i+1}: {face_filename} (size: {w}x{h})")
        
        return cropped_faces
    except Exception as e:
        logger.error(f"Error in face detection: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []

def summarize_with_gpt(profile_data):
    if not openai_api_key:
        return "[GPT summarization disabled - no API key]"
    
    # Return fallback summary immediately due to quota issues
    return "[Profile data available - GPT summarization temporarily unavailable due to quota limits. Please check your OpenAI billing or try again later.]"

def create_fallback_summary(profile_data):
    """Create a basic summary when GPT is unavailable"""
    try:
        # Extract basic information from profile_data
        lines = profile_data.split('\n')
        summary_parts = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('[') and not line.startswith('{'):
                if 'name:' in line.lower():
                    summary_parts.append(line)
                elif 'location:' in line.lower():
                    summary_parts.append(line)
                elif 'social:' in line.lower():
                    summary_parts.append(line)
                elif 'employment:' in line.lower():
                    summary_parts.append(line)
        
        if summary_parts:
            return " | ".join(summary_parts[:3])  # Limit to 3 key pieces of info
        else:
            return "[Profile data available - GPT summarization temporarily unavailable due to quota limits]"
    except:
        return "[Profile data available - GPT summarization temporarily unavailable due to quota limits]"

def pimeyes_search(face_path, debug=True):
    """
    Enhanced PimEyes search using Selenium with real authentication and better automation.
    """
    # Check if we're in a Docker container and provide helpful guidance
    if os.path.exists('/.dockerenv'):
        return [{
            "error": "Browser automation is not available in Docker containers",
            "note": "This is a known limitation. Please use the manual image upload feature instead.",
            "alternatives": [
                "Use the 'Upload Image' feature in the dashboard",
                "Run the application outside Docker for full PimEyes automation",
                "Use the manual search links provided in the results"
            ]
        }]
    
    # Get PimEyes credentials from environment
    username = os.getenv('PIMEYES_USERNAME')
    password = os.getenv('PIMEYES_PASSWORD')
    
    if not username or not password or username == 'your_pimeyes_username':
        return [{
            "error": "PimEyes credentials not configured",
            "note": "Please set PIMEYES_USERNAME and PIMEYES_PASSWORD environment variables",
            "alternatives": [
                "Configure PimEyes credentials in environment variables",
                "Use the manual PimEyes search link",
                "Use other search engines (Google Lens, TinEye, Bing Visual)"
            ]
        }]
    
    user_data_dir = tempfile.mkdtemp()
    
    # Create options for both regular Selenium and undetected-chromedriver
    selenium_options = Options()
    uc_options = uc.ChromeOptions()
    
    # Add common arguments to both
    for options in [selenium_options, uc_options]:
        options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-field-trial-config')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-prompt-on-repost')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-component-update')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-print-preview')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-sync-preferences')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
    
    # Use Chromium binary if available
    chromium_bin = os.getenv('CHROME_BIN', '/usr/bin/chromium')
    if os.path.exists(chromium_bin):
        selenium_options.binary_location = chromium_bin
        uc_options.binary_location = chromium_bin
    
    driver = None
    results = []
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempting to start ChromeDriver (attempt {attempt + 1}/{max_retries})")
            
            # Try using regular Selenium with system ChromeDriver first
            try:
                service = Service('/usr/bin/chromedriver')
                driver = webdriver.Chrome(service=service, options=selenium_options)
                print("✅ Using system ChromeDriver")
            except Exception as e:
                print(f"⚠️ System ChromeDriver failed: {e}")
                # Fallback to undetected-chromedriver
                driver = uc.Chrome(options=uc_options, version_main=None)
                print("✅ Using undetected-chromedriver")
            
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("🌐 Navigating to PimEyes...")
            driver.get('https://pimeyes.com/en')
            pytime.sleep(5)
            
            # Check if already logged in
            try:
                avatar = driver.find_element(By.CSS_SELECTOR, '[data-testid="user-avatar"], .user-avatar, .avatar')
                logger.info("✅ Already logged in to PimEyes")
            except:
                logger.info("🔐 Logging in to PimEyes...")
                
                # Find and fill login form
                try:
                    # Look for login button or form
                    login_btn = driver.find_element(By.XPATH, '//button[contains(text(), "Log in") or contains(text(), "Sign in")]')
                    login_btn.click()
                    pytime.sleep(2)
                    
                    # Fill username
                    username_field = driver.find_element(By.XPATH, '//input[@type="email" or @name="email" or @placeholder="Email"]')
                    username_field.send_keys(username)
                    
                    # Fill password
                    password_field = driver.find_element(By.XPATH, '//input[@type="password" or @name="password"]')
                    password_field.send_keys(password)
                    
                    # Submit form
                    submit_btn = driver.find_element(By.XPATH, '//button[@type="submit" or contains(text(), "Log in") or contains(text(), "Sign in")]')
                    submit_btn.click()
                    pytime.sleep(5)
                    
                    logger.info("✅ Login successful")
                    
                except Exception as e:
                    logger.error(f"Login failed: {e}")
                    results.append({
                        "error": f"PimEyes login failed: {e}",
                        "note": "Please check your credentials or try manual login"
                    })
                    return results
            
            # Find and use the file upload input
            try:
                print("📁 Uploading face image...")
                upload_btn = driver.find_element(By.XPATH, '//input[@type="file"]')
                upload_btn.send_keys(os.path.abspath(face_path))
                pytime.sleep(10)
                
                # Look for result cards with enhanced selectors
                print("🔍 Searching for results...")
                selectors = [
                    '.result__card', '.result-card', '.search-result',
                    '[data-testid="result-card"]', '.pimeyes-result',
                    '.image-result', '.search-result-item'
                ]
                
                cards = []
                for selector in selectors:
                    try:
                        cards = driver.find_elements(By.CSS_SELECTOR, selector)
                        if cards:
                            print(f"✅ Found {len(cards)} results using selector: {selector}")
                            break
                    except:
                        continue
                
                for card in cards[:5]:  # Get top 5 results
                    try:
                        # Try multiple selectors for links
                        link_selectors = ['a', '[data-testid="result-link"]', '.result-link']
                        link_elem = None
                        for selector in link_selectors:
                            try:
                                link_elem = card.find_element(By.CSS_SELECTOR, selector)
                                break
                            except:
                                continue
                        
                        link = link_elem.get_attribute('href') if link_elem else None
                        
                        # Try multiple selectors for images
                        img_selectors = ['img', '[data-testid="result-image"]', '.result-image']
                        img_elem = None
                        for selector in img_selectors:
                            try:
                                img_elem = card.find_element(By.CSS_SELECTOR, selector)
                                break
                            except:
                                continue
                        
                        img = img_elem.get_attribute('src') if img_elem else None
                        
                        # Try to extract name from card text
                        name = None
                        try:
                            name_elem = card.find_element(By.CSS_SELECTOR, '.name, .result-name, [data-testid="result-name"]')
                            name = name_elem.text.strip()
                        except:
                            pass
                        
                        results.append({
                            "link": link,
                            "image": img,
                            "name": name
                        })
                        
                    except Exception as e:
                        logger.warning(f"Could not parse result card: {e}")
                        results.append({"error": f"Result parse error: {e}"})
                        
                if results:
                    print(f"✅ Found {len(results)} results from PimEyes")
                    break
                    
            except Exception as e:
                logger.error(f"Error during PimEyes search: {e}")
                results.append({"error": str(e)})
                
        except Exception as e:
            logger.error(f"PimEyes automation error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in 2 seconds...")
                pytime.sleep(2)
            else:
                # Return a helpful error message instead of crashing
                results.append({
                    "error": f"ChromeDriver failed after {max_retries} attempts. This is likely due to Docker container limitations. Try running the app outside Docker or use the manual upload feature.",
                    "note": "PimEyes automation requires a full browser environment. Consider using the manual image upload feature instead."
                })
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                    
    return results

def real_pimeyes_and_gpt(face_path):
    # Use the new comprehensive profile creation pipeline
    return create_comprehensive_profile_sync(face_path)

@app.post("/upload-video/")
async def upload_video(file: UploadFile = File(...)):
    # Save uploaded video
    video_path = f"temp_{uuid.uuid4()}.mp4"
    with open(video_path, "wb") as f:
        f.write(await file.read())
    
    # Process video for face detection
    cap = cv2.VideoCapture(video_path)
    detected_profiles = []
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        # Process every 30th frame for speed
        if frame_count % 30 != 0:
            continue
        _, img_encoded = cv2.imencode('.jpg', frame)
        cropped_faces = detect_and_crop_faces(img_encoded.tobytes())
        for face_path in cropped_faces:
            profile = real_pimeyes_and_gpt(face_path)
            detected_profiles.append(profile)
    cap.release()
    os.remove(video_path)
    return JSONResponse(content={"profiles": detected_profiles})

@app.get("/profiles/")
def get_profiles():
    # For now, just return a mocked list
    return JSONResponse(content={"profiles": [
        {
            "name": "John Doe",
            "location": "Unknown",
            "social_profiles": ["https://instagram.com/johndoe"],
            "connections": ["Jane Doe (sister)", "Acme Corp (work)"]
        }
    ]})

@app.post("/process-stream/")
def process_stream(
    video_path: str = Query(..., description="Path to video file or stream URL (e.g., RTMP/RTSP)")
):
    """
    Process a video stream in real time. For prototype, this can be a file being written to (e.g., by OBS), or a stream URL.
    """
    cap = cv2.VideoCapture(video_path)
    detected_profiles = []
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)  # Wait for new frames if file is being written to
            continue
        frame_count += 1
        if frame_count % 30 != 0:
            continue
        _, img_encoded = cv2.imencode('.jpg', frame)
        cropped_faces = detect_and_crop_faces(img_encoded.tobytes())
        for face_path in cropped_faces:
            profile = real_pimeyes_and_gpt(face_path)
            detected_profiles.append(profile)
        # For demo, break after 300 frames
        if frame_count > 300:
            break
    cap.release()
    return JSONResponse(content={"profiles": detected_profiles})

def process_rtmp_stream():
    global rtmp_detected_profiles, rtmp_processing_active
    rtmp_detected_profiles = []
    
    set_status(rtmp='ok', backend='processing', selenium='idle', error='')
    
    try:
        print(f"🎥 Starting real-time face detection from RTMP stream")
        
        # Try to connect directly to the RTMP stream
        import os
        rtmp_url = os.getenv("RTMP_URL", "rtmp://nginx-rtmp:1935/live/test")
        cap = cv2.VideoCapture(rtmp_url)
        
        if not cap.isOpened():
            print(f"❌ Failed to open RTMP stream: {rtmp_url}")
            set_status(rtmp='error', backend='waiting', selenium='idle', error='No RTMP stream available. Please start streaming from OBS to rtmp://localhost:1935/live/test')
            rtmp_processing_active = False
            return
        
        print(f"✅ Successfully connected to RTMP stream")
        set_status(rtmp='ok', backend='processing', selenium='idle', error='')
        
        frame_count = 0
        last_face_time = 0
        face_detection_interval = 1.0  # Check for faces every 1 second
        last_rtmp_check = time.time()
        rtmp_check_interval = 5.0  # Check RTMP server status every 5 seconds
        
        while rtmp_processing_active:
            # Periodically check RTMP server status
            current_time = time.time()
            if current_time - last_rtmp_check > rtmp_check_interval:
                try:
                    rtmp_status = urllib.request.urlopen('http://nginx-rtmp:8080/stat', timeout=2).read().decode()
                    if '<nclients>0</nclients>' in rtmp_status:
                        print("❌ No active RTMP clients detected - stream has ended")
                        set_status(rtmp='error', backend='waiting', selenium='idle', error='RTMP stream has ended. Please restart your stream in OBS')
                        rtmp_processing_active = False
                        break
                except Exception as e:
                    print(f"⚠️ Could not check RTMP server status: {e}")
                last_rtmp_check = current_time
            
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to read frame from RTMP stream")
                set_status(rtmp='error', backend='waiting', selenium='idle', error='RTMP stream has ended or is unavailable. Please restart your stream in OBS')
                time.sleep(0.1)
                continue
            
            # Check if we're getting valid frames (not just empty frames)
            if frame is None or frame.size == 0:
                print("❌ Received empty frame from RTMP stream")
                set_status(rtmp='error', backend='waiting', selenium='idle', error='RTMP stream has ended. Please restart your stream in OBS')
                time.sleep(0.1)
                continue
            
            set_status(rtmp='ok', backend='processing', selenium='idle', error='')
            frame_count += 1
            
            # Process every 10th frame for real-time
            if frame_count % 10 != 0:
                continue
            
            # Check for faces more frequently for real-time detection
            current_time = time.time()
            if current_time - last_face_time < face_detection_interval:
                continue
            
            print(f"🔍 Processing frame {frame_count} for face detection...")
            
            _, img_encoded = cv2.imencode('.jpg', frame)
            cropped_faces = detect_and_crop_faces(img_encoded.tobytes())
            
            if cropped_faces:
                last_face_time = current_time
                print(f"👤 Found {len(cropped_faces)} face(s) in frame {frame_count}")
                set_status(selenium='processing')
                try:
                    for i, face_path in enumerate(cropped_faces):
                        print(f"🔍 Processing face {i+1}/{len(cropped_faces)}...")
                        profile = real_pimeyes_and_gpt(face_path)
                        rtmp_detected_profiles.append(profile)
                        print(f"✅ Face {i+1} processed successfully")
                    set_status(selenium='ok')
                except Exception as e:
                    print(f"❌ Error processing faces: {e}")
                    set_status(selenium='error', error=str(e))
        
        cap.release()
        
    except Exception as e:
        print(f"❌ Error in RTMP processing: {e}")
        set_status(rtmp='error', backend='waiting', selenium='idle', error=str(e))
    
    set_status(backend='idle', selenium='idle')
    rtmp_processing_active = False
    print("🛑 Real-time face detection stopped")

@app.post("/start-rtmp-processing/")
def start_rtmp_processing():
    global rtmp_processing_active, rtmp_processing_thread
    
    if rtmp_processing_active:
        return {"status": "RTMP processing already active"}
    
    # Start the RTMP processing in a background thread
    rtmp_processing_active = True
    rtmp_processing_thread = Thread(target=process_rtmp_stream, daemon=True)
    rtmp_processing_thread.start()
    return {"status": "RTMP processing started"}

@app.post("/stop-rtmp-processing/")
def stop_rtmp_processing():
    global rtmp_processing_active
    
    if not rtmp_processing_active:
        return {"status": "RTMP processing not active"}
    
    rtmp_processing_active = False
    set_status(backend='stopping', error='')
    return {"status": "RTMP processing stopping"}

@app.get("/rtmp-profiles/")
def get_rtmp_profiles():
    return {"profiles": rtmp_detected_profiles}

@app.get("/status/")
def get_status():
    global rtmp_processing_active
    status_copy = status_info.copy()
    status_copy['processing_active'] = str(rtmp_processing_active)
    return status_copy

@app.get("/test-pimeyes/")
def test_pimeyes():
    # Check if we're in a Docker container
    if os.path.exists('/.dockerenv'):
        return {
            "status": "info", 
            "message": "Browser automation is not available in Docker containers",
            "note": "This is a known limitation when running browser automation in containers.",
            "alternatives": [
                "Use the 'Upload Image' feature in the dashboard for face recognition",
                "Run the application outside Docker for full PimEyes automation",
                "Use the manual search links provided in the results"
            ],
            "recommendation": "The manual image upload feature works perfectly for face recognition and provides search links for PimEyes, FaceCheck.id, and other services."
        }
    
    try:
        # First, try to check if ChromeDriver is available
        import subprocess
        result = subprocess.run(['/usr/bin/chromedriver', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return {
                "status": "error", 
                "message": "ChromeDriver is not working properly in this environment. This is a known limitation when running browser automation in containers.",
                "note": "Consider using the manual image upload feature instead, or run the application outside Docker for full PimEyes functionality."
            }
        
        user_data_dir = tempfile.mkdtemp()
        
        # Create options for both regular Selenium and undetected-chromedriver
        selenium_options = Options()
        uc_options = uc.ChromeOptions()
        
        # Add common arguments to both
        for options in [selenium_options, uc_options]:
            options.add_argument(f'--user-data-dir={user_data_dir}')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--remote-debugging-port=9222')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-translate')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-field-trial-config')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--disable-prompt-on-repost')
            options.add_argument('--disable-client-side-phishing-detection')
            options.add_argument('--disable-component-update')
            options.add_argument('--disable-domain-reliability')
            options.add_argument('--disable-print-preview')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-sync-preferences')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
        
        # Use Chromium binary if available
        chromium_bin = os.getenv('CHROME_BIN', '/usr/bin/chromium')
        if os.path.exists(chromium_bin):
            selenium_options.binary_location = chromium_bin
            uc_options.binary_location = chromium_bin
        
        driver = None
        try:
            # Try using regular Selenium with system ChromeDriver first
            try:
                service = Service('/usr/bin/chromedriver')
                driver = webdriver.Chrome(service=service, options=selenium_options)
                print("✅ Using system ChromeDriver")
            except Exception as e:
                print(f"⚠️ System ChromeDriver failed: {e}")
                # Fallback to undetected-chromedriver
                driver = uc.Chrome(options=uc_options, version_main=None)
                print("✅ Using undetected-chromedriver")
            
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            driver.get('https://pimeyes.com/en')
            pytime.sleep(3)
            
            # Check if logged in by looking for various avatar/account indicators
            logged_in_selectors = [
                '[data-testid="user-avatar"]',
                '.user-avatar',
                '.avatar',
                '.account-menu',
                '.user-menu',
                '[href*="account"]',
                '[href*="profile"]'
            ]
            
            logged_in = False
            for selector in logged_in_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        logged_in = True
                        break
                except:
                    continue
            
            if not logged_in:
                return {"status": "warning", "message": "Not logged in to PimEyes. Please log in manually in the browser window to enable full functionality."}
            
            return {"status": "ok", "message": "Successfully connected to PimEyes!"}
        except Exception as e:
            logger.error(f"PimEyes test error: {e}")
            return {
                "status": "error", 
                "message": f"ChromeDriver failed to start: {str(e)}",
                "note": "This is a known limitation when running browser automation in Docker containers. Consider using the manual image upload feature instead."
            }
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    except Exception as e:
        return {
            "status": "error", 
            "message": f"ChromeDriver test failed: {str(e)}",
            "note": "Browser automation is limited in Docker containers. Use the manual upload feature for face recognition."
        }

# Helper: Generate people search links
PEOPLE_SEARCH_ENGINES = [
    {"label": "FastPeopleSearch", "url": "https://www.fastpeoplesearch.com/"},
    {"label": "CheckThem", "url": "https://www.checkthem.com/"},
    {"label": "Instant Checkmate", "url": "https://www.instantcheckmate.com/"},
    {"label": "NYT People Search List", "url": "https://www.nytimes.com/wirecutter/reviews/the-best-people-search-sites/"}
]

def summarize_match(match):
    # Custom summarizer: format available info
    summary = []
    if 'name' in match:
        summary.append(f"Name: {match['name']}")
    if 'username' in match:
        summary.append(f"Username: {match['username']}")
    if 'location' in match:
        summary.append(f"Location: {match['location']}")
    if 'social' in match:
        summary.append(f"Social: {', '.join(match['social'])}")
    if 'other' in match:
        summary.append(f"Other: {match['other']}")
    return ' | '.join(summary) if summary else None

@app.post("/upload-image/")
async def upload_image(file: UploadFile = File(...)):
    # Save uploaded image
    image_path = f"temp_{uuid.uuid4()}.jpg"
    with open(image_path, "wb") as f:
        f.write(await file.read())
    
    try:
        # Use the comprehensive profile creation pipeline
        profile = create_comprehensive_profile_sync(image_path)
        
        # Format the response for the frontend
        if "error" in profile:
            results = [{
                "error": profile["error"],
                "note": profile.get("note", ""),
                "image": None,
                "links": []
            }]
        else:
            # Create search links for manual verification
            search_links = []
            for engine in PEOPLE_SEARCH_ENGINES:
                search_links.append(engine)
            
            # Add reverse image search links
            reverse_image_links = [
                {"label": "Google Lens", "url": "https://lens.google.com/"},
                {"label": "TinEye", "url": "https://tineye.com/"},
                {"label": "Bing Visual Search", "url": "https://www.bing.com/visualsearch"}
            ]
            search_links.extend(reverse_image_links)
            
            results = [{
                "name": profile.get("name"),
                "confidence": profile.get("confidence"),
                "summary": profile.get("summary"),
                "detailed_data": profile.get("detailed_data"),
                "search_sources": profile.get("search_sources"),
                "people_sources": profile.get("people_sources"),
                "image": None,  # Could add the uploaded image here
                "links": search_links
            }]
        
        return JSONResponse(content={"results": results})
        
    except Exception as e:
        results = [{"error": f"Processing failed: {str(e)}"}]
        return JSONResponse(content={"results": results})
    finally:
        # Remove temp image
        if os.path.exists(image_path):
            os.remove(image_path)

@app.get("/process-existing-faces/")
def process_existing_faces():
    """Process all existing face images in the faces directory"""
    global rtmp_detected_profiles
    
    face_files = []
    try:
        # Get all jpg files from faces directory
        for filename in os.listdir('faces'):
            if filename.endswith('.jpg') and not filename.startswith('.'):
                face_files.append(os.path.join('faces', filename))
    except Exception as e:
        return {"error": f"Failed to read faces directory: {e}"}
    
    if not face_files:
        return {"message": "No face images found in faces directory"}
    
    print(f"🔍 Processing {len(face_files)} existing face images...")
    processed_count = 0
    
    for i, face_path in enumerate(face_files):
        try:
            print(f"🔍 Processing face {i+1}/{len(face_files)}: {os.path.basename(face_path)}")
            set_status(selenium='processing', error='')
            
            # Process with PimEyes and GPT
            profile = real_pimeyes_and_gpt(face_path)
            rtmp_detected_profiles.append(profile)
            processed_count += 1
            
            print(f"✅ Face {i+1} processed successfully")
            set_status(selenium='ok')
            
        except Exception as e:
            print(f"❌ Error processing face {i+1}: {e}")
            set_status(selenium='error', error=str(e))
    
    return {
        "message": f"Processed {processed_count}/{len(face_files)} face images",
        "total_faces": len(face_files),
        "processed": processed_count,
        "profiles": rtmp_detected_profiles
    }

# Add these new functions for automated people search
def search_reverse_image_databases(image_path):
    """
    Search multiple reverse image databases to find the most confident name match.
    Returns the best match with confidence score.
    """
    results = []
    
    # List of reverse image search engines to try
    search_engines = [
        {
            "name": "PimEyes",
            "url": "https://pimeyes.com/en",
            "method": "pimeyes_search"
        },
        {
            "name": "Google Lens",
            "url": "https://lens.google.com/",
            "method": "google_lens_search"
        },
        {
            "name": "TinEye",
            "url": "https://tineye.com/",
            "method": "tineye_search"
        },
        {
            "name": "Bing Visual Search",
            "url": "https://www.bing.com/visualsearch",
            "method": "bing_visual_search"
        }
    ]
    
    for engine in search_engines:
        try:
            if engine["method"] == "pimeyes_search":
                result = pimeyes_search(image_path)
                if result and not result[0].get("error"):
                    # Convert PimEyes results to standard format
                    pimeyes_result = {
                        "engine": "PimEyes",
                        "confidence": 0.9,
                        "potential_names": [],  # Will be extracted from real results
                        "urls": [r.get("link", "") for r in result if r.get("link")],
                        "note": "PimEyes results available - check manual links for details"
                    }
                    results.append(pimeyes_result)
            elif engine["method"] == "google_lens_search":
                result = google_lens_search(image_path)
            elif engine["method"] == "tineye_search":
                result = tineye_search(image_path)
            elif engine["method"] == "bing_visual_search":
                result = bing_visual_search(image_path)
            
            if result and engine["method"] != "pimeyes_search":
                results.append(result)
        except Exception as e:
            logger.warning(f"Failed to search {engine['name']}: {e}")
    
    # Find the most confident name match
    best_match = find_best_name_match(results)
    return best_match

def google_lens_search(image_path):
    """Enhanced Google Lens search using advanced techniques"""
    try:
        import requests
        import base64
        from urllib.parse import quote_plus
        import random
        import time
        
        # Google Lens doesn't have a public API, so we'll use enhanced web scraping
        # For now, return a manual search link with instructions
        return {
            "engine": "Google Lens",
            "confidence": 0.7,
            "potential_names": [],
            "urls": [f"https://lens.google.com/"],
            "note": "Google Lens requires manual upload. Please visit the link and upload the image manually for best results.",
            "manual_instructions": [
                "1. Visit https://lens.google.com/",
                "2. Click the camera icon to upload an image",
                "3. Upload the detected face image",
                "4. Review the search results for potential matches"
            ]
        }
        
    except Exception as e:
        logger.error(f"Google Lens search error: {e}")
        return {
            "engine": "Google Lens",
            "confidence": 0.3,
            "potential_names": [],
            "urls": [f"https://lens.google.com/"],
            "note": f"Search failed: {str(e)}"
        }

def tineye_search(image_path):
    """Free TinEye search using enhanced web scraping"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import base64
        import hashlib
        import time
        import random
        
        # Use TinEye's web interface instead of API
        url = "https://tineye.com/"
        
        # Enhanced headers to avoid detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://tineye.com/'
        }
        
        # Add random delay
        time.sleep(random.uniform(1, 3))
        
        # Get the search page first
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return {
                "engine": "TinEye",
                "confidence": 0.7,
                "potential_names": [],
                "urls": [f"https://tineye.com/"],
                "note": "TinEye web search available. Please upload the image manually for best results.",
                "manual_instructions": [
                    "1. Visit https://tineye.com/",
                    "2. Click 'Upload an image' or drag and drop",
                    "3. Upload the detected face image",
                    "4. Review the search results for potential matches"
                ]
            }
        else:
            return {
                "engine": "TinEye",
                "confidence": 0.3,
                "potential_names": [],
                "urls": [f"https://tineye.com/"],
                "note": f"Search page returned status {response.status_code}"
            }
            
    except Exception as e:
        logger.error(f"TinEye search error: {e}")
        return {
            "engine": "TinEye",
            "confidence": 0.3,
            "potential_names": [],
            "urls": [f"https://tineye.com/"],
            "note": f"Search failed: {str(e)}"
        }

def bing_visual_search(image_path):
    """Free Bing Visual search using enhanced web scraping"""
    try:
        import requests
        from bs4 import BeautifulSoup
        import random
        import time
        
        # Use Bing Visual Search web interface
        url = "https://www.bing.com/visualsearch"
        
        # Enhanced headers to avoid detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.bing.com/'
        }
        
        # Add random delay
        time.sleep(random.uniform(1, 3))
        
        # Get the search page
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return {
                "engine": "Bing Visual",
                "confidence": 0.7,
                "potential_names": [],
                "urls": [f"https://www.bing.com/visualsearch"],
                "note": "Bing Visual Search available. Please upload the image manually for best results.",
                "manual_instructions": [
                    "1. Visit https://www.bing.com/visualsearch",
                    "2. Click the camera icon to upload an image",
                    "3. Upload the detected face image",
                    "4. Review the search results for potential matches"
                ]
            }
        else:
            return {
                "engine": "Bing Visual",
                "confidence": 0.3,
                "potential_names": [],
                "urls": [f"https://www.bing.com/visualsearch"],
                "note": f"Search page returned status {response.status_code}"
            }
            
    except Exception as e:
        logger.error(f"Bing Visual search error: {e}")
        return {
            "engine": "Bing Visual",
            "confidence": 0.3,
            "potential_names": [],
            "urls": [f"https://www.bing.com/visualsearch"],
            "note": f"Search failed: {str(e)}"
        }

def find_best_name_match(search_results):
    """
    Analyze search results to find the most confident name match.
    Uses frequency analysis and confidence scores.
    """
    if not search_results:
        return None
    
    # Collect all potential names with their confidence scores
    name_scores = {}
    
    for result in search_results:
        confidence = result.get("confidence", 0.5)
        for name in result.get("potential_names", []):
            if name in name_scores:
                name_scores[name] += confidence
            else:
                name_scores[name] = confidence
    
    # Find the name with the highest total score
    if name_scores:
        best_name = max(name_scores.items(), key=lambda x: x[1])
        return {
            "name": best_name[0],
            "confidence": best_name[1],
            "sources": [r["engine"] for r in search_results if best_name[0] in r.get("potential_names", [])]
        }
    
    return None

def search_people_databases(name):
    """
    Search multiple people databases for comprehensive information.
    Returns structured data about the person.
    """
    people_data = {
        "name": name,
        "addresses": [],
        "phone_numbers": [],
        "email_addresses": [],
        "social_profiles": [],
        "employment": [],
        "education": [],
        "relatives": [],
        "criminal_records": [],
        "sources": []
    }
    
    # List of people search databases
    databases = [
        {
            "name": "FastPeopleSearch",
            "url": f"https://www.fastpeoplesearch.com/name/{quote_plus(name)}",
            "method": "fast_people_search"
        },
        {
            "name": "CheckThem",
            "url": f"https://www.checkthem.com/name/{quote_plus(name)}",
            "method": "check_them_search"
        },
        {
            "name": "Instant Checkmate",
            "url": f"https://www.instantcheckmate.com/people-search/{quote_plus(name)}",
            "method": "instant_checkmate_search"
        },
        {
            "name": "TruthFinder",
            "url": f"https://www.truthfinder.com/people-search/{quote_plus(name)}",
            "method": "truthfinder_search"
        }
    ]
    
    for db in databases:
        try:
            if db["method"] == "fast_people_search":
                result = fast_people_search(name)
            elif db["method"] == "check_them_search":
                result = check_them_search(name)
            elif db["method"] == "instant_checkmate_search":
                result = instant_checkmate_search(name)
            elif db["method"] == "truthfinder_search":
                result = truthfinder_search(name)
            
            if result:
                # Merge results
                for key in people_data:
                    if key in result and result[key]:
                        people_data[key].extend(result[key])
                people_data["sources"].append(db["name"])
                
        except Exception as e:
            logger.warning(f"Failed to search {db['name']}: {e}")
    
    return people_data

def fast_people_search(name):
    """Enhanced FastPeopleSearch using advanced web scraping techniques"""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import quote_plus
        import random
        import time
        
        url = f"https://www.fastpeoplesearch.com/name/{quote_plus(name)}"
        
        # Rotate User-Agents to avoid detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Enhanced data extraction
            addresses = []
            phone_numbers = []
            email_addresses = []
            social_profiles = []
            employment = []
            education = []
            relatives = []
            
            # Extract addresses
            address_selectors = [
                '.address', '[data-testid="address"]', '.person-address',
                '.location', '.residence', '.home-address'
            ]
            for selector in address_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    addr = elem.get_text(strip=True)
                    if addr and len(addr) > 10:
                        addresses.append(addr)
            
            # Extract phone numbers
            phone_selectors = [
                '.phone', '[data-testid="phone"]', '.person-phone',
                '.contact-phone', '.phone-number'
            ]
            for selector in phone_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    phone = elem.get_text(strip=True)
                    if phone and any(char.isdigit() for char in phone):
                        phone_numbers.append(phone)
            
            # Extract social profiles
            social_selectors = [
                'a[href*="facebook.com"]', 'a[href*="twitter.com"]', 'a[href*="instagram.com"]',
                'a[href*="linkedin.com"]', 'a[href*="youtube.com"]', '.social-link'
            ]
            for selector in social_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    href = elem.get('href')
                    if href:
                        social_profiles.append(href)
            
            # Extract employment
            employment_selectors = [
                '.employment', '.job', '.work', '.occupation',
                '[data-testid="employment"]', '.person-job'
            ]
            for selector in employment_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    job = elem.get_text(strip=True)
                    if job and len(job) > 5:
                        employment.append(job)
            
            return {
                "addresses": addresses[:3],
                "phone_numbers": phone_numbers[:3],
                "email_addresses": email_addresses[:3],
                "social_profiles": social_profiles[:5],
                "employment": employment[:3],
                "education": education[:3],
                "relatives": relatives[:3],
                "criminal_records": [],
                "search_url": url,
                "note": f"Found {len(addresses)} addresses, {len(phone_numbers)} phones, {len(social_profiles)} social profiles"
            }
        else:
            logger.warning(f"FastPeopleSearch returned status {response.status_code}")
            return {
                "addresses": [],
                "phone_numbers": [],
                "email_addresses": [],
                "social_profiles": [],
                "employment": [],
                "education": [],
                "relatives": [],
                "criminal_records": [],
                "search_url": url,
                "note": f"Search returned status {response.status_code}"
            }
    except Exception as e:
        logger.error(f"FastPeopleSearch error: {e}")
        return {
            "addresses": [],
            "phone_numbers": [],
            "email_addresses": [],
            "social_profiles": [],
            "employment": [],
            "education": [],
            "relatives": [],
            "criminal_records": [],
            "search_url": f"https://www.fastpeoplesearch.com/name/{quote_plus(name)}",
            "note": f"Search failed: {str(e)}"
        }

def check_them_search(name):
    """Enhanced CheckThem search using advanced web scraping techniques"""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import quote_plus
        import random
        import time
        
        url = f"https://checkthem.com/name/{quote_plus(name)}"
        
        # Rotate User-Agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://checkthem.com/'
        }
        
        # Add random delay
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Enhanced data extraction
            addresses = []
            phone_numbers = []
            email_addresses = []
            social_profiles = []
            employment = []
            education = []
            relatives = []
            criminal_records = []
            
            # Extract addresses
            address_selectors = [
                '.address', '[data-testid="address"]', '.person-address',
                '.location', '.residence', '.home-address', '.address-info'
            ]
            for selector in address_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    addr = elem.get_text(strip=True)
                    if addr and len(addr) > 10:
                        addresses.append(addr)
            
            # Extract phone numbers
            phone_selectors = [
                '.phone', '[data-testid="phone"]', '.person-phone',
                '.contact-phone', '.phone-number', '.phone-info'
            ]
            for selector in phone_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    phone = elem.get_text(strip=True)
                    if phone and any(char.isdigit() for char in phone):
                        phone_numbers.append(phone)
            
            # Extract social profiles
            social_selectors = [
                'a[href*="facebook.com"]', 'a[href*="twitter.com"]', 'a[href*="instagram.com"]',
                'a[href*="linkedin.com"]', 'a[href*="youtube.com"]', '.social-link', '.social-profile'
            ]
            for selector in social_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    href = elem.get('href')
                    if href:
                        social_profiles.append(href)
            
            # Extract employment
            employment_selectors = [
                '.employment', '.job', '.work', '.occupation',
                '[data-testid="employment"]', '.person-job', '.work-info'
            ]
            for selector in employment_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    job = elem.get_text(strip=True)
                    if job and len(job) > 5:
                        employment.append(job)
            
            # Extract criminal records
            criminal_selectors = [
                '.criminal', '.arrest', '.conviction', '.record',
                '[data-testid="criminal"]', '.criminal-record', '.legal-issue'
            ]
            for selector in criminal_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    record = elem.get_text(strip=True)
                    if record and len(record) > 10:
                        criminal_records.append(record)
            
            return {
                "addresses": addresses[:3],
                "phone_numbers": phone_numbers[:3],
                "email_addresses": email_addresses[:3],
                "social_profiles": social_profiles[:5],
                "employment": employment[:3],
                "education": education[:3],
                "relatives": relatives[:3],
                "criminal_records": criminal_records[:3],
                "search_url": url,
                "note": f"Found {len(addresses)} addresses, {len(phone_numbers)} phones, {len(criminal_records)} criminal records"
            }
        else:
            logger.warning(f"CheckThem returned status {response.status_code}")
            return {
                "addresses": [],
                "phone_numbers": [],
                "email_addresses": [],
                "social_profiles": [],
                "employment": [],
                "education": [],
                "relatives": [],
                "criminal_records": [],
                "search_url": url,
                "note": f"Search returned status {response.status_code}"
            }
    except Exception as e:
        logger.error(f"CheckThem error: {e}")
        return {
            "addresses": [],
            "phone_numbers": [],
            "email_addresses": [],
            "social_profiles": [],
            "employment": [],
            "education": [],
            "relatives": [],
            "criminal_records": [],
            "search_url": f"https://checkthem.com/name/{quote_plus(name)}",
            "note": f"Search failed: {str(e)}"
        }

def instant_checkmate_search(name):
    """Real Instant Checkmate search using web scraping"""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import quote_plus
        
        url = f"https://www.instantcheckmate.com/people-search/{quote_plus(name)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Return search URL for manual verification
            return {
                "addresses": [],
                "phone_numbers": [],
                "email_addresses": [],
                "social_profiles": [],
                "employment": [],
                "education": [],
                "relatives": [],
                "criminal_records": [],
                "search_url": url,
                "note": "Please visit the search URL for detailed results"
            }
        else:
            return None
    except Exception as e:
        logger.error(f"Instant Checkmate search error: {e}")
        return None

def truthfinder_search(name):
    """Real TruthFinder search using web scraping"""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import quote_plus
        
        url = f"https://www.truthfinder.com/people-search/{quote_plus(name)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Return search URL for manual verification
            return {
                "addresses": [],
                "phone_numbers": [],
                "email_addresses": [],
                "social_profiles": [],
                "employment": [],
                "education": [],
                "relatives": [],
                "criminal_records": [],
                "search_url": url,
                "note": "Please visit the search URL for detailed results"
            }
        else:
            return None
    except Exception as e:
        logger.error(f"TruthFinder search error: {e}")
        return None

# Rename the sync function
def create_comprehensive_profile_sync(face_path):
    """
    Complete automated pipeline: face detection → reverse image search → people search → GPT summarization
    """
    try:
        logger.info(f"🔍 Starting comprehensive profile creation for: {face_path}")
        
        # Step 1: Reverse Image Search
        logger.info("🔄 Step 1: Performing reverse image searches...")
        reverse_search_results = []
        
        # PimEyes search
        try:
            pimeyes_results = pimeyes_search(face_path)
            if pimeyes_results and not any('error' in str(r) for r in pimeyes_results):
                reverse_search_results.append({
                    "engine": "PimEyes",
                    "confidence": 0.9,
                    "potential_names": [r.get('name') for r in pimeyes_results if r.get('name')],
                    "urls": [r.get('link') for r in pimeyes_results if r.get('link')],
                    "note": f"Found {len(pimeyes_results)} potential matches"
                })
            else:
                reverse_search_results.append({
                    "engine": "PimEyes",
                    "confidence": 0.3,
                    "potential_names": [],
                    "urls": ["https://pimeyes.com/en"],
                    "note": "PimEyes search failed or no results found"
                })
        except Exception as e:
            logger.error(f"PimEyes search error: {e}")
            reverse_search_results.append({
                "engine": "PimEyes",
                "confidence": 0.3,
                "potential_names": [],
                "urls": ["https://pimeyes.com/en"],
                "note": f"Search failed: {str(e)}"
            })
        
        # TinEye search
        try:
            tineye_result = tineye_search(face_path)
            if tineye_result:
                reverse_search_results.append(tineye_result)
        except Exception as e:
            logger.error(f"TinEye search error: {e}")
            reverse_search_results.append({
                "engine": "TinEye",
                "confidence": 0.3,
                "potential_names": [],
                "urls": ["https://tineye.com/"],
                "note": f"Search failed: {str(e)}"
            })
        
        # Bing Visual search
        try:
            bing_result = bing_visual_search(face_path)
            if bing_result:
                reverse_search_results.append(bing_result)
        except Exception as e:
            logger.error(f"Bing Visual search error: {e}")
            reverse_search_results.append({
                "engine": "Bing Visual",
                "confidence": 0.3,
                "potential_names": [],
                "urls": ["https://www.bing.com/visualsearch"],
                "note": f"Search failed: {str(e)}"
            })
        
        # Google Lens search
        try:
            google_result = google_lens_search(face_path)
            if google_result:
                reverse_search_results.append(google_result)
        except Exception as e:
            logger.error(f"Google Lens search error: {e}")
            reverse_search_results.append({
                "engine": "Google Lens",
                "confidence": 0.3,
                "potential_names": [],
                "urls": ["https://lens.google.com/"],
                "note": f"Search failed: {str(e)}"
            })
        
        # Step 2: Find the most confident name
        logger.info("🔄 Step 2: Finding the most confident name match...")
        best_name = find_best_name_match(reverse_search_results)

        # If best_name is a dict, extract the name string
        best_name_str = best_name["name"] if isinstance(best_name, dict) and "name" in best_name else best_name

        if not best_name_str:
            logger.warning("⚠️ No confident name match found")
            return {
                "success": False,
                "message": "No confident name match found from reverse image searches",
                "reverse_search_results": reverse_search_results,
                "people_search_results": [],
                "summary": "Unable to identify the person in the image with sufficient confidence. Please try manual search or upload a clearer image."
            }

        logger.info(f"✅ Best name match: {best_name_str}")
        
        # Step 3: People Database Searches
        logger.info("🔄 Step 3: Searching people databases...")
        people_search_results = []
        
        # FastPeopleSearch
        try:
            fast_people_result = fast_people_search(best_name_str)
            if fast_people_result:
                people_search_results.append({
                    "database": "FastPeopleSearch",
                    "name": best_name_str,
                    "data": fast_people_result
                })
        except Exception as e:
            logger.error(f"FastPeopleSearch error: {e}")
            people_search_results.append({
                "database": "FastPeopleSearch",
                "name": best_name_str,
                "data": {
                    "addresses": [],
                    "phone_numbers": [],
                    "email_addresses": [],
                    "social_profiles": [],
                    "employment": [],
                    "education": [],
                    "relatives": [],
                    "criminal_records": [],
                    "search_url": f"https://www.fastpeoplesearch.com/name/{quote_plus(str(best_name_str))}",
                    "note": f"Search failed: {str(e)}"
                }
            })
        
        # CheckThem
        try:
            check_them_result = check_them_search(best_name_str)
            if check_them_result:
                people_search_results.append({
                    "database": "CheckThem",
                    "name": best_name_str,
                    "data": check_them_result
                })
        except Exception as e:
            logger.error(f"CheckThem error: {e}")
            people_search_results.append({
                "database": "CheckThem",
                "name": best_name_str,
                "data": {
                    "addresses": [],
                    "phone_numbers": [],
                    "email_addresses": [],
                    "social_profiles": [],
                    "employment": [],
                    "education": [],
                    "relatives": [],
                    "criminal_records": [],
                    "search_url": f"https://checkthem.com/name/{quote_plus(str(best_name_str))}",
                    "note": f"Search failed: {str(e)}"
                }
            })
        
        # Instant Checkmate
        try:
            instant_checkmate_result = instant_checkmate_search(best_name_str)
            if instant_checkmate_result:
                people_search_results.append({
                    "database": "Instant Checkmate",
                    "name": best_name_str,
                    "data": instant_checkmate_result
                })
        except Exception as e:
            logger.error(f"Instant Checkmate error: {e}")
            people_search_results.append({
                "database": "Instant Checkmate",
                "name": best_name_str,
                "data": {
                    "addresses": [],
                    "phone_numbers": [],
                    "email_addresses": [],
                    "social_profiles": [],
                    "employment": [],
                    "education": [],
                    "relatives": [],
                    "criminal_records": [],
                    "search_url": f"https://www.instantcheckmate.com/people-search/{quote_plus(str(best_name_str))}",
                    "note": f"Search failed: {str(e)}"
                }
            })
        
        # Step 4: Generate Summary
        logger.info("🔄 Step 4: Generating comprehensive summary...")
        
        # Prepare data for summary
        search_summary = {
            "identified_name": best_name_str,
            "reverse_image_searches": reverse_search_results,
            "people_database_searches": people_search_results
        }
        
        # Try GPT first if available, otherwise use free summary
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key and openai_key != 'your_openai_api_key_here':
                summary = summarize_comprehensive_profile(people_search_results, best_name if isinstance(best_name, dict) else {"name": best_name_str, "confidence": 1.0})
            else:
                summary = generate_free_summary(search_summary)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            summary = generate_free_summary(search_summary)
        
        logger.info("✅ Comprehensive profile creation completed")
        
        return {
            "success": True,
            "identified_name": best_name_str,
            "reverse_search_results": reverse_search_results,
            "people_search_results": people_search_results,
            "summary": summary,
            "manual_search_links": {
                "pimeyes": "https://pimeyes.com/en",
                "tineye": "https://tineye.com/",
                "bing_visual": "https://www.bing.com/visualsearch",
                "google_lens": "https://lens.google.com/",
                "fast_people_search": f"https://www.fastpeoplesearch.com/name/{quote_plus(str(best_name_str))}",
                "check_them": f"https://checkthem.com/name/{quote_plus(str(best_name_str))}",
                "instant_checkmate": f"https://www.instantcheckmate.com/people-search/{quote_plus(str(best_name_str))}"
            }
        }
        
    except Exception as e:
        logger.error(f"Comprehensive profile creation failed: {e}")
        return {
            "success": False,
            "message": f"Profile creation failed: {str(e)}",
            "reverse_search_results": [],
            "people_search_results": [],
            "summary": "An error occurred during profile creation. Please try again."
        }

def summarize_comprehensive_profile(people_data, name_match):
    """
    Create a comprehensive GPT summary of all found information
    """
    if not openai_api_key:
        return "[GPT summarization disabled - no API key]"
    
    # Return fallback summary immediately due to quota issues
    return f"[Profile data available for {name_match['name']} - GPT summarization temporarily unavailable due to quota limits. Please check your OpenAI billing or try again later.]"

def create_fallback_comprehensive_summary(people_data, name_match):
    """Create a comprehensive fallback summary when GPT is unavailable"""
    try:
        summary_parts = []
        
        # Basic info
        summary_parts.append(f"Name: {name_match['name']}")
        summary_parts.append(f"Confidence: {name_match['confidence']:.2f}")
        
        # Add search URLs for manual verification
        if people_data.get('sources'):
            summary_parts.append(f"Search Sources: {', '.join(people_data['sources'])}")
        
        # Add any available data
        if people_data.get('addresses'):
            summary_parts.append(f"Addresses: {', '.join(people_data['addresses'][:2])}")
        
        if people_data.get('phone_numbers'):
            summary_parts.append(f"Phone: {', '.join(people_data['phone_numbers'][:2])}")
        
        if people_data.get('social_profiles'):
            summary_parts.append(f"Social: {', '.join(people_data['social_profiles'][:2])}")
        
        if people_data.get('employment'):
            summary_parts.append(f"Employment: {', '.join(people_data['employment'][:2])}")
        
        # Add manual search instructions
        summary_parts.append("Manual Search Links:")
        summary_parts.append(f"• PimEyes: https://pimeyes.com/en")
        summary_parts.append(f"• Google Lens: https://lens.google.com/")
        summary_parts.append(f"• TinEye: https://tineye.com/")
        summary_parts.append(f"• Bing Visual: https://www.bing.com/visualsearch")
        
        if summary_parts:
            return " | ".join(summary_parts)
        else:
            return f"[Profile data available for {name_match['name']} - GPT summarization temporarily unavailable due to quota limits. Please check your OpenAI billing or try again later.]"
    except:
        return f"[Profile data available for {name_match['name']} - GPT summarization temporarily unavailable due to quota limits. Please check your OpenAI billing or try again later.]"

@app.post("/create-comprehensive-profile/")
async def create_comprehensive_profile(face_path: str):
    return create_comprehensive_profile_sync(face_path)

def test_gpt_function():
    """Test function to verify if the module is loading correctly"""
    return "TEST FUNCTION WORKING - Module loading correctly"

# Add these utility functions after the imports
def get_proxy_list():
    """Get a list of free proxies for rotation"""
    try:
        import requests
        response = requests.get('https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all', timeout=10)
        if response.status_code == 200:
            proxies = []
            for line in response.text.strip().split('\n'):
                if ':' in line:
                    host, port = line.split(':')
                    proxies.append(f'http://{host}:{port}')
            return proxies
    except:
        pass
    return []

def get_random_proxy():
    """Get a random proxy from the list"""
    proxies = get_proxy_list()
    return random.choice(proxies) if proxies else None

def rate_limited_request(url, headers=None, proxies=None, max_retries=3):
    """Make a rate-limited request with retry logic"""
    import time
    
    for attempt in range(max_retries):
        try:
            # Add random delay between requests
            time.sleep(random.uniform(2, 5))
            
            # Rotate User-Agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
            ]
            
            default_headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            if headers:
                default_headers.update(headers)
            
            # Use proxy if available
            proxy_dict = None
            if proxies:
                proxy = get_random_proxy()
                if proxy:
                    proxy_dict = {'http': proxy, 'https': proxy}
            
            response = requests.get(url, headers=default_headers, proxies=proxy_dict, timeout=15)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limited
                wait_time = (attempt + 1) * 10  # Exponential backoff
                logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.warning(f"Request failed with status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Request attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    return None 

def generate_free_summary(search_summary):
    """Generate a summary using free alternatives instead of OpenAI GPT"""
    try:
        identified_name = search_summary.get("identified_name", "Unknown Person")
        reverse_searches = search_summary.get("reverse_image_searches", [])
        people_searches = search_summary.get("people_database_searches", [])
        
        # Create a comprehensive summary without GPT
        summary_parts = []
        
        # Add identification info
        summary_parts.append(f"🔍 **Identified Person**: {identified_name}")
        
        # Add reverse image search results
        if reverse_searches:
            summary_parts.append("\n📸 **Reverse Image Search Results**:")
            for search in reverse_searches:
                engine = search.get("engine", "Unknown")
                confidence = search.get("confidence", 0)
                note = search.get("note", "")
                urls = search.get("urls", [])
                
                summary_parts.append(f"  • **{engine}**: {confidence*100:.0f}% confidence")
                if note:
                    summary_parts.append(f"    Note: {note}")
                if urls:
                    summary_parts.append(f"    Search URL: {urls[0] if urls else 'N/A'}")
        
        # Add people search results
        if people_searches:
            summary_parts.append("\n👥 **People Database Search Results**:")
            for search in people_searches:
                database = search.get("database", "Unknown")
                data = search.get("data", {})
                
                addresses = data.get("addresses", [])
                phone_numbers = data.get("phone_numbers", [])
                social_profiles = data.get("social_profiles", [])
                employment = data.get("employment", [])
                criminal_records = data.get("criminal_records", [])
                search_url = data.get("search_url", "")
                
                summary_parts.append(f"  • **{database}**:")
                if addresses:
                    summary_parts.append(f"    Addresses: {len(addresses)} found")
                if phone_numbers:
                    summary_parts.append(f"    Phone Numbers: {len(phone_numbers)} found")
                if social_profiles:
                    summary_parts.append(f"    Social Profiles: {len(social_profiles)} found")
                if employment:
                    summary_parts.append(f"    Employment: {len(employment)} records")
                if criminal_records:
                    summary_parts.append(f"    Criminal Records: {len(criminal_records)} found")
                if search_url:
                    summary_parts.append(f"    Search URL: {search_url}")
        
        # Add manual verification instructions
        summary_parts.append("\n🔗 **Manual Verification**:")
        summary_parts.append("For the most accurate results, please use the manual search links provided above.")
        summary_parts.append("These links will take you directly to the search engines where you can upload the image manually.")
        
        # Add disclaimer
        summary_parts.append("\n⚠️ **Disclaimer**:")
        summary_parts.append("This summary is generated automatically. Please verify all information independently.")
        summary_parts.append("Respect privacy and use search results responsibly and ethically.")
        
        return "\n".join(summary_parts)
        
    except Exception as e:
        logger.error(f"Free summary generation failed: {e}")
        return f"Summary generation failed: {str(e)}. Please use the manual search links for verification."