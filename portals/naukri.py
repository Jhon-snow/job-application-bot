import time
import logging
import hashlib

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

logger = logging.getLogger(__name__)

TITLE_SELECTOR = "div.text-title18Sb.text-n100"
TITLE_WAIT_TIMEOUT = 15

JS_EXTRACT_JOBS = """
const titles = document.querySelectorAll('.text-title18Sb.text-n100');
const jobs = [];
titles.forEach((titleEl, idx) => {
    const titleText = titleEl.textContent.trim();

    // Skip non-title text that leaks in (sidebar filters, etc.)
    if (/^\\d+\\s*(years?|yrs)$/i.test(titleText)) return;
    if (titleText.length < 4) return;

    let card = titleEl;
    for (let i = 0; i < 10; i++) {
        if (!card.parentElement) break;
        card = card.parentElement;
        if (card.textContent.includes('Yrs') && card.querySelector('a[href]')) break;
    }

    const links = card.querySelectorAll('a[href]');
    let jobLink = '';
    for (const a of links) {
        const href = a.href || '';
        if (href.includes('job-listings') || href.includes('/job/')) {
            jobLink = href;
            break;
        }
    }
    if (!jobLink) {
        for (const a of links) {
            const href = a.href || '';
            if (href.includes('naukri.com') && !href.includes('company')
                && !href.includes('/search') && href !== window.location.href) {
                jobLink = href;
                break;
            }
        }
    }

    const text = card.innerText || '';
    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

    let location = '';
    let experience = '';
    let company = '';
    let salary = '';

    for (const line of lines) {
        if (/\\d+-\\d+\\s*Yrs|\\d+\\+?\\s*Yrs/i.test(line) && !experience) {
            experience = line;
        }
        else if (/Bengaluru|Bangalore|Hyderabad|Pune|Mumbai|Chennai|Remote|Noida|Gurgaon|Gurugram|Secunderabad|Delhi|Kolkata/i.test(line) && !location) {
            location = line;
        }
        else if (/^Hybrid/i.test(line) && !location) {
            location = line;
        }
        else if (/₹|Lakhs?|Cr|Not Disclosed/i.test(line) && !salary) {
            salary = line;
        }
    }

    const titleIdx = lines.indexOf(titleText);
    if (titleIdx > 0) {
        for (let i = titleIdx - 1; i >= 0; i--) {
            const l = lines[i];
            if (l && !l.match(/^\\d/) && !l.match(/ago$/) && l.length > 2
                && l !== 'Quick apply' && !l.includes('employees')
                && !l.includes('Posted') && !l.includes('Hiring for')
                && !l.match(/Reviews?$/) && !l.match(/^\\d+\\.\\d+$/)
                && !l.match(/^(Software Product|IT |Recruitment|Internet|Financial|Film|Advertising)/)) {
                company = l;
                break;
            }
        }
    }

    jobs.push({
        title: titleText,
        company: company,
        location: location,
        experience: experience,
        salary: salary,
        link: jobLink,
        index: idx
    });
});
return jobs;
"""


def check_already_logged_in(driver: webdriver.Chrome) -> bool:
    driver.get("https://www.naukri.com")
    time.sleep(4)

    page_text = driver.page_source.lower()
    logged_in_markers = ["naukri 360", "minis feed", "activity"]
    if any(marker in page_text for marker in logged_in_markers):
        return True

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text[:500].lower()
        if "login" in body_text and "register" in body_text:
            return False
        if "home" in body_text and "activity" in body_text:
            return True
    except Exception:
        pass

    return False


def login(driver: webdriver.Chrome, email: str, password: str) -> bool:
    logger.info("Logging into Naukri...")
    driver.get("https://www.naukri.com/nlogin/login")
    time.sleep(3)

    try:
        email_field = driver.find_element(
            By.XPATH,
            "//input[@type='text' and @placeholder='Enter your active Email ID / Username']",
        )
        email_field.clear()
        email_field.send_keys(email)

        pass_field = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_field.clear()
        pass_field.send_keys(password)

        login_btn = driver.find_element(
            By.XPATH, "//button[@type='submit' and contains(text(),'Login')]"
        )
        login_btn.click()
        time.sleep(5)

        if "naukri.com" in driver.current_url and "login" not in driver.current_url:
            logger.info("Naukri login successful")
            return True

        logger.error(f"Naukri login may have failed. URL: {driver.current_url}")
        return False

    except Exception as e:
        logger.error(f"Naukri login failed: {e}")
        return False


def search_jobs(driver: webdriver.Chrome, keyword: str, location: str = "") -> list[dict]:
    encoded_keyword = keyword.replace(" ", "-").lower()
    encoded_location = location.lower() if location else ""

    url = f"https://www.naukri.com/{encoded_keyword}-jobs"
    if encoded_location:
        url += f"-in-{encoded_location}"
    url += "?experience=5"

    logger.info(f"Searching Naukri: {keyword} in {location or 'any location'}")
    driver.get(url)

    _dismiss_popups(driver)

    if not _wait_for_titles(driver):
        logger.warning(f"No job titles found. Title: {driver.title}")
        return []

    raw_jobs = driver.execute_script(JS_EXTRACT_JOBS)
    if not raw_jobs:
        logger.warning("JS extraction returned no jobs")
        return []

    logger.info(f"Found {len(raw_jobs)} jobs on Naukri")

    jobs = []
    title_elements = driver.find_elements(By.CSS_SELECTOR, TITLE_SELECTOR)

    for raw in raw_jobs:
        idx = raw.get("index", -1)
        title = raw.get("title", "")
        link = raw.get("link", "")
        job_id = _make_job_id(title, raw.get("company", ""), link)

        element = title_elements[idx] if 0 <= idx < len(title_elements) else None

        jobs.append({
            "title": title,
            "company": raw.get("company", ""),
            "location": raw.get("location", ""),
            "experience": raw.get("experience", ""),
            "description": "",
            "link": link,
            "job_id": f"naukri_{job_id}",
            "title_element": element,
        })

    return jobs


def _wait_for_titles(driver: webdriver.Chrome) -> bool:
    try:
        WebDriverWait(driver, TITLE_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, TITLE_SELECTOR))
        )
        time.sleep(2)
        return True
    except TimeoutException:
        _dismiss_popups(driver)
        time.sleep(3)
        titles = driver.find_elements(By.CSS_SELECTOR, TITLE_SELECTOR)
        return len(titles) > 0


def _make_job_id(title: str, company: str, link: str) -> str:
    if link:
        slug = link.rstrip("/").split("/")[-1].split("?")[0]
        if slug and len(slug) > 5:
            return slug
    raw = f"{title}_{company}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _dismiss_popups(driver: webdriver.Chrome):
    popup_close_selectors = [
        "button[aria-label='Close']",
        ".styles_close__sOacC",
        "#login_Layer .crossIcon",
        ".chatbot_closeBtn",
        "button.close",
        "[data-dismiss='modal']",
    ]
    for sel in popup_close_selectors:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.5)
        except Exception:
            continue


def apply_to_job(driver: webdriver.Chrome, job: dict) -> bool:
    """Click the title element to open side panel, then find and click apply."""
    title_el = job.get("title_element")
    if not title_el:
        logger.warning(f"No clickable element for: {job['title']}")
        return False

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});"
            "arguments[0].click();",
            title_el,
        )
        time.sleep(3)

        apply_btn = _find_apply_button(driver)
        if not apply_btn:
            logger.info(f"No apply button for: {job['title']} at {job['company']}")
            return False

        initial_handles = set(driver.window_handles)
        try:
            apply_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", apply_btn)
        time.sleep(4)

        current_handles = set(driver.window_handles)
        new_tabs = current_handles - initial_handles
        if new_tabs:
            new_tab = new_tabs.pop()
            driver.switch_to.window(new_tab)
            logger.info(f"External apply opened for: {job['title']} at {job['company']}")
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return True

        if _check_applied_confirmation(driver):
            logger.info(f"Applied on Naukri: {job['title']} at {job['company']}")
            return True

        _handle_chatbot_questions(driver)
        time.sleep(2)

        if _check_applied_confirmation(driver):
            logger.info(f"Applied on Naukri: {job['title']} at {job['company']}")
            return True

        logger.warning(f"Apply clicked but unconfirmed for: {job['title']}")
        return True

    except Exception as e:
        logger.error(f"Error applying to {job.get('title', '?')}: {e}")
        return False


def _find_apply_button(driver: webdriver.Chrome):
    """Find Quick Apply / Apply button using multiple strategies."""
    xpaths = [
        "//*[contains(text(),'Quick apply') or contains(text(),'quick apply')]",
        "//button[contains(text(),'Apply')]",
        "//a[contains(text(),'Apply')]",
        "//*[contains(text(),'Apply on company')]",
        "//button[contains(@class,'apply')]",
        "//a[contains(@class,'apply')]",
    ]
    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed() and el.is_enabled():
                    return el
        except Exception:
            continue

    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = (btn.text or "").strip().lower()
            if "apply" in text and btn.is_displayed():
                return btn
    except Exception:
        pass

    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            text = (link.text or "").strip().lower()
            if "apply" in text and link.is_displayed():
                return link
    except Exception:
        pass

    return None


def _check_applied_confirmation(driver: webdriver.Chrome) -> bool:
    confirmation_texts = [
        "applied successfully", "already applied", "application sent",
        "you have already applied", "application submitted",
        "apply success", "your application",
    ]
    page_text = driver.page_source.lower()
    if any(text in page_text for text in confirmation_texts):
        return True

    try:
        driver.find_element(
            By.XPATH,
            "//*[contains(@class,'applied') or contains(@class,'success')]",
        )
        return True
    except NoSuchElementException:
        return False


def _handle_chatbot_questions(driver: webdriver.Chrome):
    try:
        submit_buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(text(),'Submit') or contains(text(),'Save') or contains(text(),'Continue')]",
        )
        for btn in submit_buttons:
            try:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
            except Exception:
                continue
    except Exception:
        pass
