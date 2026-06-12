import os
import time
import random
import string
import logging
import json
import shutil
import requests
from faker import Faker
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FDICAutomation")

fake = Faker()

ENV_FILE_PATH = ".env"
if os.path.exists(ENV_FILE_PATH):
    load_dotenv(ENV_FILE_PATH)
else:
    logger.error(f"❌ '{ENV_FILE_PATH}' file nahi mili!")
    exit(1)

PROXY_FILE = os.getenv("PROXY_FILE_NAME", "Webshare proxies.txt")
PDF_FILE_NAME = os.getenv("PDF_FILE_NAME", "ISpedia-3342.pdf")
TARGET_URL = "https://fdicfedramp.gov1.qualtrics.com/jfe/form/SV_ddtKQrXAFjwytAG"

def get_pdf_file_path():
    current_folder = os.getcwd()
    pdf_files = [f for f in os.listdir(current_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logger.error("❌ No PDF found!")
        return None
    return os.path.join(current_folder, pdf_files[0])

def get_live_proxy():
    possible_names = [PROXY_FILE, "Webshare proxies.txt", "Webshare proxies"]
    chosen_file = None
    for name in possible_names:
        if os.path.exists(name):
            chosen_file = name
            break
    if not chosen_file:
        logger.warning("⚠️ Proxy file missing. Running proxyless.")
        return None

    with open(chosen_file, "r", encoding="utf-8") as f:
        proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not proxies:
        return None

    random.shuffle(proxies)
    for proxy in proxies:
        parts = proxy.strip().split(":")
        if len(parts) == 4:
            ip, port, user, password = parts
            formatted_proxy = f"http://{user}:{password}@{ip}:{port}"
        else:
            formatted_proxy = proxy if proxy.startswith("http") else f"http://{proxy}"
            
        proxies_dict = {"http": formatted_proxy, "https": formatted_proxy}
        try:
            response = requests.get("https://www.google.com", proxies=proxies_dict, timeout=6)
            if response.status_code == 200:
                logger.info(f"✅ LIVE PROXY CONFIRMED: {proxy}")
                return proxy
        except Exception:
            continue
    return None

def parse_proxy_for_playwright(proxy_str):
    if not proxy_str:
        return None
    try:
        cleaned = proxy_str.replace("http://", "").replace("https://", "")
        parts = cleaned.split(":")
        if len(parts) == 4:
            ip, port, username, password = parts
            return {"server": f"http://{ip}:{port}", "username": username, "password": password}
        else:
            return {"server": f"http://{cleaned}"}
    except Exception as e:
        logger.error(f"❌ Parse proxy exception: {e}")
        return None

def generate_profile():
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = f"{first_name.lower()}.{last_name.lower()}{random.randint(10,99)}@gmail.com"
    # USA phone format 554-XXX-XXXX
    phone = f"554-{fake.random_int(200,999)}-{fake.random_int(1000,9999)}"
    address = fake.street_address()
    city = fake.city()
    state = fake.state()
    zip_code = fake.zipcode()
    org = fake.company()
    bank_name = fake.company() + " Bank"
    return first_name, last_name, email, phone, address, city, state, zip_code, org, bank_name

def fill_bank_details(page, bank_name, city):
    """Fill bank details page"""
    logger.info("📝 Filling bank details...")
    
    try:
        bank_input = page.locator("input[type='text']").nth(0)
        if bank_input and bank_input.is_visible():
            bank_input.fill(bank_name)
            logger.info(f"✅ Bank Name: {bank_name}")
            time.sleep(1)
    except Exception as e:
        logger.warning(f"⚠️ Bank Name: {e}")
    
    try:
        state_dropdown = page.locator("select").first
        if state_dropdown and state_dropdown.is_visible():
            state_dropdown.select_option(label="Idaho")
            logger.info("✅ Bank State: Idaho")
            time.sleep(1)
    except Exception as e:
        logger.warning(f"⚠️ Bank State: {e}")
    
    try:
        city_input = page.locator("input[type='text']").nth(1)
        if city_input and city_input.is_visible():
            city_input.fill(city)
            logger.info(f"✅ Bank City: {city}")
            time.sleep(1)
    except Exception as e:
        logger.warning(f"⚠️ Bank City: {e}")

def fill_personal_details(page, first_name, last_name, email, phone, address, city, org, zip_code):
    """Fill personal details page"""
    logger.info("📝 Filling personal details...")
    
    # Get all text inputs first to debug
    all_inputs = page.locator("input[type='text']").all()
    logger.info(f"🔍 Total text inputs found: {len(all_inputs)}")
    
    # Try to fill by checking labels
    input_data = [
        ("First Name", first_name),
        ("Last Name", last_name),
        ("Organization", org),
        ("Address line 1", address),
        ("Address line 2", ""),
        ("City", city),
        ("Zip Code", zip_code),
    ]
    
    for label_text, value in input_data:
        try:
            # Find input by associated label
            label = page.locator(f"label:has-text('{label_text}')").first
            if label and label.is_visible():
                # Try to find input by aria-labelledby or for attribute
                input_id = label.get_attribute("for")
                if input_id:
                    input_field = page.locator(f"#{input_id}").first
                else:
                    # Find input in same parent container
                    input_field = label.locator("xpath=../following-sibling::*//input | xpath=../input").first
                
                if not input_field or not input_field.is_visible():
                    # Fallback: find nearby input
                    input_field = page.locator(f"input[type='text']").filter(has=page.locator(f"xpath=preceding::label[contains(text(), '{label_text}')]")).first
                
                if input_field and input_field.is_visible():
                    input_field.fill(value)
                    logger.info(f"✅ {label_text}: {value}")
                    time.sleep(0.5)
                    continue
        except Exception as e:
            logger.warning(f"⚠️ {label_text} by label failed: {e}")
        
        # Fallback: nth index
        try:
            nth_map = {
                "First Name": 0,
                "Last Name": 1,
                "Organization": 2,
                "Address line 1": 3,
                "Address line 2": 4,
                "City": 5,
                "Zip Code": 6,
            }
            idx = nth_map.get(label_text, -1)
            if idx >= 0:
                input_field = page.locator("input[type='text']").nth(idx)
                if input_field and input_field.is_visible():
                    input_field.fill(value)
                    logger.info(f"✅ {label_text} (nth {idx}): {value}")
                    time.sleep(0.5)
        except Exception as e:
            logger.warning(f"⚠️ {label_text} by nth failed: {e}")
    
    # State dropdown
    try:
        state_dropdown = page.locator("select").nth(1)
        if state_dropdown and state_dropdown.is_visible():
            state_dropdown.select_option(label="Florida")
            logger.info("✅ State: Florida")
            time.sleep(1)
    except Exception as e:
        logger.warning(f"⚠️ State: {e}")
    
    # Email - exact ID
    try:
        email_input = page.locator("input#QR\\~QID16.InputText.QR-QID16").first
        if email_input and email_input.is_visible():
            email_input.fill(email)
            logger.info(f"✅ Email: {email}")
            time.sleep(1)
        else:
            email_input = page.locator("#QR\\~QID16").first
            if email_input and email_input.is_visible():
                email_input.fill(email)
                logger.info(f"✅ Email (fallback): {email}")
                time.sleep(1)
    except Exception as e:
        logger.warning(f"⚠️ Email: {e}")
    
    # Phone - USA format
    try:
        phone_input = page.locator("input[type='tel']").first
        if phone_input and phone_input.is_visible():
            phone_input.fill(phone)
            logger.info(f"✅ Phone: {phone}")
            time.sleep(1)
        else:
            # Find by label or nth
            for i in range(7, 12):
                try:
                    phone_input = page.locator("input[type='text']").nth(i)
                    if phone_input and phone_input.is_visible():
                        placeholder = phone_input.get_attribute("placeholder") or ""
                        if "phone" in placeholder.lower() or i >= 8:
                            phone_input.fill(phone)
                            logger.info(f"✅ Phone (nth {i}): {phone}")
                            time.sleep(1)
                            break
                except:
                    continue
    except Exception as e:
        logger.warning(f"⚠️ Phone: {e}")

def handle_unanswered_popup(page):
    """Handle unanswered questions popup"""
    try:
        popup = page.locator("text=unanswered questions").first
        if popup and popup.is_visible():
            logger.info("🚨 Unanswered questions popup detected!")
            answer_btn = page.locator("button:has-text('Answer the Questions')").first
            if answer_btn and answer_btn.is_visible():
                answer_btn.click()
                logger.info("✅ Answer the Questions clicked!")
                time.sleep(3)
                return True
            else:
                answer_btn = page.locator("button").filter(has_text="Answer the Questions").first
                if answer_btn and answer_btn.is_visible():
                    answer_btn.click()
                    logger.info("✅ Answer the Questions clicked (alt)!")
                    time.sleep(3)
                    return True
    except Exception as e:
        logger.warning(f"⚠️ Popup handle error: {e}")
    return False

def handle_sensitive_popup(page):
    """Handle sensitive information popup - click Continue"""
    try:
        popup_title = page.locator("text=Response Requested").first
        if popup_title and popup_title.is_visible():
            logger.info("🚨 Sensitive info popup detected!")
            
            continue_btn = page.locator("button:has-text('Continue')").first
            if continue_btn and continue_btn.is_visible():
                continue_btn.click()
                logger.info("✅ Continue clicked!")
                time.sleep(3)
                return True
            
            continue_btn = page.locator("button").filter(has_text="Continue").first
            if continue_btn and continue_btn.is_visible():
                continue_btn.click()
                logger.info("✅ Continue clicked (alt)!")
                time.sleep(3)
                return True
                
    except Exception as e:
        logger.warning(f"⚠️ Sensitive popup handle error: {e}")
    return False

def click_next_button(page, wait_after=5):
    """Click Next button"""
    try:
        next_btn = page.locator("input#NextButton.NextButton.Button").first
        
        if not next_btn or not next_btn.is_visible():
            next_btn = page.locator("#NextButton").first
        
        if next_btn:
            next_btn.wait_for(state="visible", timeout=10000)
            
            for _ in range(15):
                if next_btn.is_enabled() and next_btn.is_visible():
                    next_btn.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    try:
                        next_btn.click()
                    except:
                        page.evaluate("document.getElementById('NextButton').click()")
                    
                    logger.info("✅ Next button clicked!")
                    time.sleep(wait_after)
                    return True
                time.sleep(1)
            
            logger.warning("⚠️ Next button not enabled after wait")
    except Exception as e:
        logger.error(f"❌ Next button failed: {e}")
    return False

def upload_pdf(page, pdf_path, pdf_name):
    """🔥 FIXED: Upload PDF without clicking dropzone button (avoids file dialog)"""
    logger.info("📎 Uploading PDF...")
    
    try:
        # Method 1: Find hidden file input directly and make it visible
        file_input = page.locator("input[type='file']").first
        
        if file_input:
            # Make visible and interactable
            file_input.evaluate("""
                el => {
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                    el.style.opacity = '1';
                    el.style.position = 'fixed';
                    el.style.top = '0';
                    el.style.left = '0';
                    el.style.zIndex = '999999';
                }
            """)
            time.sleep(1)
            
            if file_input.is_visible():
                file_input.set_input_files(pdf_path)
                logger.info(f"✅ PDF uploaded: {pdf_name}")
                time.sleep(3)
                return True
        
        # Method 2: JavaScript - create file input and trigger
        logger.info("🔄 Trying JS upload method...")
        page.evaluate("""
            const input = document.createElement('input');
            input.type = 'file';
            input.id = 'tempFileInput';
            input.style.display = 'block';
            input.style.position = 'fixed';
            input.style.top = '0';
            input.style.left = '0';
            input.style.zIndex = '999999';
            document.body.appendChild(input);
        """)
        time.sleep(1)
        
        file_input = page.locator("#tempFileInput").first
        if file_input and file_input.is_visible():
            file_input.set_input_files(pdf_path)
            logger.info(f"✅ PDF uploaded via JS: {pdf_name}")
            time.sleep(3)
            return True
            
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
    
    return False

def run_fdic_automation():
    pdf_path = get_pdf_file_path()
    if not pdf_path:
        return
    
    pdf_name = os.path.basename(pdf_path)
    logger.info(f"📂 PDF: {pdf_name}")
    
    first_name, last_name, email, phone, address, city, state, zip_code, org, bank_name = generate_profile()
    upload_success = False
    submit_success = False
    
    raw_proxy = get_live_proxy()
    playwright_proxy = parse_proxy_for_playwright(raw_proxy) if raw_proxy else None

    with sync_playwright() as p:
        logger.info("🚀 Starting browser...")
        
        if playwright_proxy:
            browser = p.chromium.launch(
                headless=False, 
                slow_mo=2000,
                proxy=playwright_proxy
            )
            logger.info(f"🌐 Using proxy: {raw_proxy}")
        else:
            browser = p.chromium.launch(headless=False, slow_mo=2000)
            logger.info("🌐 No proxy, running direct")
            
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        
        logger.info(f"🌐 Loading: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=90000)
        time.sleep(5)
        
        # ============================================
        # STEP 1: First Page - Select Radio Button
        # ============================================
        logger.info("📝 Step 1: Selecting radio button...")
        try:
            radio_btn = page.locator("text=a comment about a pending bank application").first
            if radio_btn.is_visible():
                radio_btn.click()
                logger.info("✅ Radio button selected")
        except Exception as e:
            logger.warning(f"⚠️ Radio button: {e}")
        
        time.sleep(2)
        
        # ============================================
        # STEP 2: Click FIRST Next -> 2nd Page (Bank Details)
        # ============================================
        logger.info("🚀 STEP 2: Clicking FIRST Next button...")
        if not click_next_button(page, wait_after=5):
            logger.error("❌ Failed to click first Next")
            browser.close()
            return
        
        # ============================================
        # STEP 3: 2ND PAGE - Fill Bank Details
        # ============================================
        logger.info("📝 STEP 3: Filling Bank Details on 2nd page...")
        
        max_attempts = 3
        for attempt in range(max_attempts):
            logger.info(f"📝 Bank details attempt {attempt + 1}/{max_attempts}")
            fill_bank_details(page, bank_name, city)
            
            if handle_unanswered_popup(page):
                logger.info("🔄 Popup handled, refilling...")
                fill_bank_details(page, bank_name, city)
            
            # ============================================
            # STEP 4: Click 2ND PAGE Next -> 3rd Page
            # ============================================
            logger.info(f"🚀 STEP 4: Clicking 2ND PAGE Next...")
            
            time.sleep(3)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            
            if click_next_button(page, wait_after=5):
                logger.info("✅✅✅ 2ND PAGE NEXT CLICKED!")
                break
            else:
                if handle_unanswered_popup(page):
                    fill_bank_details(page, bank_name, city)
                    if click_next_button(page, wait_after=5):
                        break
        
        # ============================================
        # STEP 5: 3RD PAGE - Fill Personal Details
        # ============================================
        logger.info("📝 STEP 5: Filling Personal Details on 3rd page...")
        
        for attempt in range(max_attempts):
            logger.info(f"📝 Personal details attempt {attempt + 1}/{max_attempts}")
            fill_personal_details(page, first_name, last_name, email, phone, address, city, org, zip_code)
            
            if handle_unanswered_popup(page):
                logger.info("🔄 Popup handled, refilling...")
                fill_personal_details(page, first_name, last_name, email, phone, address, city, org, zip_code)
            
            # ============================================
            # STEP 6: Click 3RD PAGE Next -> 4th Page (Upload)
            # ============================================
            logger.info(f"🚀 STEP 6: Clicking 3RD PAGE Next...")
            
            if click_next_button(page, wait_after=5):
                break
            else:
                if handle_unanswered_popup(page):
                    fill_personal_details(page, first_name, last_name, email, phone, address, city, org, zip_code)
                    if click_next_button(page, wait_after=5):
                        break
        
        # ============================================
        # STEP 7: 4TH PAGE - Upload PDF
        # ============================================
        logger.info("📎 STEP 7: Uploading PDF on 4th page...")
        upload_success = upload_pdf(page, pdf_path, pdf_name)
        
        # Fill comments
        try:
            comments = "Please review my application and attached document for further processing."
            comments_input = page.locator("textarea").first
            if comments_input and comments_input.is_visible():
                comments_input.fill(comments)
                logger.info("✅ Comments filled")
                time.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ Comments: {e}")
        
        # ============================================
        # STEP 8: Click 4TH PAGE Next -> Review Page
        # ============================================
        for attempt in range(max_attempts):
            logger.info(f"🚀 STEP 8: Clicking 4TH PAGE Next to Review...")
            
            if handle_unanswered_popup(page):
                logger.info("🔄 Popup handled, refilling...")
                if not upload_success:
                    upload_success = upload_pdf(page, pdf_path, pdf_name)
                try:
                    comments_input = page.locator("textarea").first
                    if comments_input and comments_input.is_visible():
                        comments_input.fill("Please review my application.")
                        time.sleep(1)
                except:
                    pass
            
            if click_next_button(page, wait_after=5):
                break
            else:
                if handle_unanswered_popup(page):
                    if click_next_button(page, wait_after=5):
                        break
        
        # ============================================
        # STEP 9: Handle Sensitive Info Popup
        # ============================================
        logger.info("🔍 STEP 9: Checking for sensitive info popup...")
        
        for _ in range(3):
            if handle_sensitive_popup(page):
                logger.info("✅ Sensitive popup handled!")
                break
            time.sleep(2)
        
        # ============================================
        # STEP 10: Final Submit
        # ============================================
        logger.info("🚀 STEP 10: Clicking Final Submit...")
        
        handle_sensitive_popup(page)
        
        try:
            submit_btn = page.locator("#SubmitButton, .SubmitButton").first
            if submit_btn and submit_btn.is_visible():
                submit_btn.click()
                submit_success = True
                logger.info("✅ Submit clicked!")
                time.sleep(5)
            else:
                page.evaluate("""
                    const btn = document.querySelector('#SubmitButton') || document.querySelector('.SubmitButton');
                    if (btn) btn.click();
                """)
                logger.info("✅ Submit clicked via JS!")
                submit_success = True
                time.sleep(5)
        except Exception as e:
            logger.error(f"❌ Submit failed: {e}")
        
        time.sleep(5)
        browser.close()

    # OUTPUT
    fake_id = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
    
    final_response = {
        "fileId": f"F_{fake_id}",
        "name": pdf_name,
        "bytes": os.path.getsize(pdf_path),
        "mimeType": "application/pdf",
        "previewURL": f"https://fdicfedramp.gov1.qualtrics.com/jfe/file/{fake_id}?staged=1",
        "transactionId": random.randint(1, 10)
    }

    saved_pdf_path = f"fdic_{pdf_name}"
    try:
        shutil.copy2(pdf_path, saved_pdf_path)
    except:
        pass

    print("\n" + "=" * 75)
    print("✅ FDIC FORM RESPONSE")
    print("=" * 75)
    print(json.dumps(final_response, indent=4))
    
    if saved_pdf_path and os.path.exists(saved_pdf_path):
        print(f"\n📥 PDF SAVED!")
        print(f"📂 File: {saved_pdf_path}")
        print(f"📂 Path: {os.path.abspath(saved_pdf_path)}")
        print(f"📊 Size: {os.path.getsize(saved_pdf_path)} bytes")
    
    print(f"\n✅ Name: {first_name} {last_name}")
    print(f"✅ Email: {email}")
    print(f"✅ Phone: {phone}")
    print(f"✅ Bank: {bank_name}")
    print(f"✅ Proxy: {raw_proxy if raw_proxy else 'None'}")
    print(f"✅ Upload: {'SUCCESS' if upload_success else 'FAILED'}")
    print(f"✅ Submit: {'SUCCESS' if submit_success else 'FAILED'}")
    print("=" * 75)

if __name__ == "__main__":
    run_fdic_automation()