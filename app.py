from flask import Flask, request, jsonify, send_file, render_template
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    WebDriverException, StaleElementReferenceException,
    InvalidSessionIdException
)
from webdriver_manager.firefox import GeckoDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import threading
import os
import csv
import time
import random

app = Flask(__name__)

# ── BLACKLISTED WEBSITE DOMAINS ────────────────────────────────────────────────
# If a company's website matches any of these, the Website field is cleared
# but the company record (name, phone, address, etc.) is still kept.
BLACKLISTED_DOMAINS = {
    "indiamart.com", "justdial.com", "tradeindia.com",
    "facebook.com", "instagram.com", "youtube.com",
    "whatsapp.com", "gmail.com"
}

LOCATIONS = {
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur",
                   "Tirunelveli", "Erode", "Vellore", "Thoothukudi", "Dindigul", "Thanjavur",
                   "Hosur", "Nagercoil", "Kancheepuram"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati", "Kurnool", "Nellore",
                       "Rajahmundry", "Kakinada", "Eluru", "Anantapur", "Kadapa", "Ongole",
                       "Chittoor", "Machilipatnam", "Tenali", "Hindupur", "Proddatur", "Adoni",
                       "Nandyal", "Srikakulam", "Vizianagaram", "Tadepalligudem", "Bhimavaram",
                       "Narasaraopet", "Amalapuram", "Gudivada", "Dharmavaram", "Madanapalle",
                       "Palakollu", "Kavali", "Tadipatri", "Rayachoti", "Puttur", "Chirala"],
    "Telangana": ["Hyderabad", "Warangal", "Khammam", "Nizamabad", "Karimnagar", "Ramagundam",
                  "Mahabubnagar", "Nalgonda", "Adilabad", "Suryapet", "Siddipet", "Miryalaguda",
                  "Jagtial", "Mancherial", "Kamareddy", "Bodhan", "Sangareddy", "Medak",
                  "Vikarabad", "Zaheerabad", "Bhongir", "Wanaparthy", "Gadwal", "Kothagudem",
                  "Palwancha", "Bellampalli", "Korutla", "Tandur", "Kagaznagar", "Husnabad"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Dharwad", "Belagavi",
                  "Kalaburagi", "Ballari", "Shivamogga", "Tumakuru", "Davanagere", "Vijayapura",
                  "Udupi", "Raichur", "Hassan"],
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Kollam", "Kannur",
               "Alappuzha", "Kottayam", "Palakkad", "Malappuram"],
    "Delhi NCR": ["New Delhi", "Delhi", "Gurugram", "Noida", "Greater Noida", "Faridabad",
                  "Ghaziabad", "Sonipat", "Bahadurgarh"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali", "Moga",
               "Pathankot", "Hoshiarpur", "Kapurthala"],
    "Haryana": ["Panipat", "Ambala", "Yamunanagar", "Hisar", "Rohtak",
                "Karnal","Panchkula"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Satna",
                       "Ratlam", "Rewa", "Dewas"],
    "Himachal Pradesh": ["Shimla", "Solan", "Dharamshala", "Mandi", "Baddi", "Parwanoo",
                         "Hamirpur", "Una", "Bilaspur", "Kullu"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Agra", "Varanasi", "Prayagraj", "Meerut",
                       "Gorakhpur", "Bareilly", "Aligarh"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Kharagpur",
                    "Haldia", "Bardhaman", "Malda", "Berhampore"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Durg", "Bilaspur", "Korba", "Raigarh", "Jagdalpur",
                     "Rajnandgaon", "Ambikapur", "Dhamtari"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri",
               "Balasore", "Bhadrak", "Jharsuguda", "Jeypore"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar", "Hazaribagh",
                  "Giridih", "Ramgarh", "Medininagar", "Chaibasa"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner", "Alwar",
                  "Bharatpur", "Sri Ganganagar", "Pali"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar",
                "Gandhinagar", "Anand", "Morbi", "Junagadh"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Thane", "Navi Mumbai",
                    "Kolhapur", "Solapur", "Amravati"]
}

# ── GLOBAL STATE ──────────────────────────────────────────────────────────────
progress_lock      = threading.Lock()
csv_write_lock     = threading.Lock()
global_seen_lock   = threading.Lock()
global_seen_phones = set()

progress = {
    "status": "idle", "current": "", "done": 0,
    "total": 0, "log": [], "file": "", "companies_found": 0
}

# 4GB RAM Linux — change to 2 if you want faster
MAX_WORKERS = 2


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _log(msg):
    with progress_lock:
        progress["log"].append(msg)
        if len(progress["log"]) > 300:
            progress["log"] = progress["log"][-300:]


def _inc(label, n):
    with progress_lock:
        progress["done"]           += 1
        progress["current"]         = label
        progress["companies_found"] += n


def _is_driver_alive(driver):
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def _quit_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass


# ── DRIVER: Linux Firefox ─────────────────────────────────────────────────────
def _make_driver():
    options = Options()
    options.add_argument("--headless")
    options.set_preference("permissions.default.image", 2)
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.cache.memory.enable", False)
    options.set_preference("javascript.options.mem.max", 512)
    options.set_preference(
        "general.useragent.override",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
    )
    service = Service(GeckoDriverManager().install())
    driver  = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(60)
    return driver


# ── SCRAPE ONE CITY ───────────────────────────────────────────────────────────
def scrape_city(driver, category, city, state):
    results = []
    query   = f"{category} service providers in {city} {state}"
    url     = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="feed"]'))
        )
    except TimeoutException:
        _log(f"  ⏭ No results: {city}, {state}")
        return results

    # Scroll to load all cards
    last_count = 0
    no_change  = 0

    while True:
        try:
            feed = driver.find_element(By.XPATH, '//div[@role="feed"]')
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollTop + 2000;", feed
            )
        except StaleElementReferenceException:
            try:
                feed = driver.find_element(By.XPATH, '//div[@role="feed"]')
            except Exception:
                break
        except Exception:
            break

        time.sleep(1.5)

        try:
            driver.find_element(
                By.XPATH, '//*[contains(text(),"reached the end")]'
            )
            break
        except NoSuchElementException:
            pass

        try:
            count = len(driver.find_elements(
                By.XPATH, '//div[@role="feed"]//a[@href]'
            ))
        except Exception:
            break

        if count == last_count:
            no_change += 1
            if no_change >= 3:
                break
        else:
            no_change = 0
        last_count = count

    # Collect all links
    try:
        anchors = driver.find_elements(
            By.XPATH, '//div[@role="feed"]//a[@href]'
        )
    except Exception:
        return results

    links, names = [], []
    for a in anchors:
        try:
            href  = a.get_attribute("href")
            label = a.get_attribute("aria-label")
            if href and "/maps/place/" in href and label and href not in links:
                links.append(href)
                names.append(label.strip())
        except StaleElementReferenceException:
            continue

    # Visit each company page
    for i, link in enumerate(links):
        try:
            driver.get(link)
            time.sleep(1.5)

            # Phone
            phone = ""
            try:
                pb = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'button[data-item-id^="phone:tel:"]')
                    )
                )
                phone = pb.get_attribute("data-item-id").replace("phone:tel:", "").strip()
            except TimeoutException:
                try:
                    pb    = driver.find_element(
                        By.XPATH, '//button[contains(@aria-label,"Phone")]'
                    )
                    phone = pb.get_attribute("aria-label").replace("Phone: ", "").strip()
                except NoSuchElementException:
                    phone = ""

            # Global dedup by phone
            if phone:
                with global_seen_lock:
                    if phone in global_seen_phones:
                        continue
                    global_seen_phones.add(phone)

            # Address
            address = ""
            try:
                ab      = driver.find_element(
                    By.CSS_SELECTOR, 'button[data-item-id="address"]'
                )
                address = ab.text.strip()
            except NoSuchElementException:
                try:
                    ab      = driver.find_element(
                        By.XPATH, '//button[contains(@aria-label,"Address")]'
                    )
                    address = ab.get_attribute("aria-label").replace("Address: ", "").strip()
                except NoSuchElementException:
                    address = f"{city}, {state}"

            # Website
            website = ""
            try:
                wb      = driver.find_element(
                    By.CSS_SELECTOR, 'a[data-item-id="authority"]'
                )
                website = wb.get_attribute("href")
            except NoSuchElementException:
                website = ""

            # Blacklist check — skip only the website field, keep the record
            if website and any(b in website.lower() for b in BLACKLISTED_DOMAINS):
                website = ""

            results.append({
                "Company Name": names[i],
                "Phone Number": phone,
                "Address":      address,
                "Website":      website,
                "City":         city,
                "State":        state,
                "Category":     category
            })

        except (InvalidSessionIdException, WebDriverException):
            raise

    return results


# ── STATE WORKER ──────────────────────────────────────────────────────────────
def scrape_state_batch(state, cities, category, csv_path):
    driver      = None
    total_found = 0

    driver = _make_driver()

    for city in cities:
        _log(f"🔍 {city}, {state}")

        if not _is_driver_alive(driver):
            _log(f"  🔄 Driver dead before {city} — restarting...")
            _quit_driver(driver)
            time.sleep(5)
            driver = _make_driver()

        try:
            city_results = scrape_city(driver, category, city, state)

        except (InvalidSessionIdException, WebDriverException) as e:
            _log(f"  ⚠️ Firefox crashed at {city} — restarting...")
            _quit_driver(driver)
            time.sleep(5)
            try:
                driver       = _make_driver()
                city_results = scrape_city(driver, category, city, state)
                _log(f"  ✅ Retry success: {city}")
            except Exception as retry_e:
                _log(f"  ❌ Retry failed {city}: {retry_e}")
                city_results = []
                _quit_driver(driver)
                time.sleep(3)
                try:
                    driver = _make_driver()
                except Exception:
                    pass

        except Exception as e:
            _log(f"  ❌ {city} error: {e}")
            city_results = []

        total_found += len(city_results)

        if city_results:
            with csv_write_lock:
                file_exists = os.path.exists(csv_path)
                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        "Company Name", "Phone Number", "Address",
                        "Website", "City", "State", "Category"
                    ])
                    if not file_exists:
                        writer.writeheader()
                    writer.writerows(city_results)

        _inc(f"{city}, {state}", len(city_results))
        _log(f"  ✅ {city} — {len(city_results)} companies")

        with progress_lock:
            done_so_far = progress["done"]
        if done_so_far % 10 == 0 and os.path.exists(csv_path):
            try:
                with csv_write_lock:
                    df_p = pd.read_csv(csv_path)
                df_p.to_excel(
                    csv_path.replace(".csv", "_PARTIAL.xlsx"), index=False
                )
            except Exception:
                pass

        time.sleep(random.uniform(3, 6))

    _quit_driver(driver)
    return total_found


# ── MAIN ORCHESTRATOR ─────────────────────────────────────────────────────────
def run_scraper(category):
    global progress, global_seen_phones

    csv_path  = f"{category.replace(' ', '_')}_results.csv"
    xlsx_path = f"{category.replace(' ', '_')}_results.xlsx"

    with global_seen_lock:
        global_seen_phones.clear()

    if os.path.exists(csv_path):
        os.remove(csv_path)

    total_cities = sum(len(c) for c in LOCATIONS.values())

    with progress_lock:
        progress.update({
            "status": "running", "current": "", "done": 0,
            "total": total_cities, "log": [], "file": "",
            "companies_found": 0
        })

    grand_total = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                scrape_state_batch, state, cities, category, csv_path
            ): state
            for state, cities in LOCATIONS.items()
        }
        for future in as_completed(futures):
            state = futures[future]
            try:
                count = future.result()
                grand_total += count
                _log(f"✅ {state} done — {count} companies")
            except Exception as e:
                _log(f"  ❌ {state} failed: {e}")

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df.drop_duplicates(subset=["Phone Number"],         keep="first", inplace=True)
        df.drop_duplicates(subset=["Company Name", "City"], keep="first", inplace=True)
        df.to_excel(xlsx_path, index=False)
        try:
            os.remove(csv_path)
        except Exception:
            pass

    with progress_lock:
        progress["status"] = "done"
        progress["file"]   = xlsx_path
        progress["log"].append(f"🎉 Done! {grand_total} companies saved.")


# ── FLASK ROUTES ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    with progress_lock:
        if progress["status"] == "running":
            return jsonify({"error": "Scraping already in progress"}), 400

    data     = request.json or {}
    category = data.get("category", "").strip()
    if not category:
        return jsonify({"error": "Category is required"}), 400

    with progress_lock:
        progress.update({
            "status": "starting", "current": "", "done": 0,
            "total": 0, "log": [], "file": "", "companies_found": 0
        })

    t = threading.Thread(target=run_scraper, args=(category,))
    t.daemon = True
    t.start()
    return jsonify({"message": "Scraping started"})


@app.route("/progress")
def get_progress():
    with progress_lock:
        return jsonify(dict(progress))


@app.route("/download")
def download():
    fp = progress.get("file", "")
    if fp and os.path.exists(fp):
        return send_file(fp, as_attachment=True)
    return jsonify({"error": "File not ready"}), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
