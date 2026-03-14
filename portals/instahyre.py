import time
import hashlib
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

logger = logging.getLogger(__name__)

BASE_URL = "https://www.instahyre.com"


def check_already_logged_in(driver: webdriver.Chrome) -> bool:
    driver.get(f"{BASE_URL}/candidate/opportunities/")
    time.sleep(4)
    url = driver.current_url
    if "opportunities" in url and "login" not in url:
        return True
    return False


def login(driver: webdriver.Chrome, email: str = "", password: str = "") -> bool:
    """Instahyre login. SSO users must log in manually once via the browser."""
    driver.get(f"{BASE_URL}/login/")
    time.sleep(3)

    if email and password:
        try:
            email_field = driver.find_element(By.NAME, "email")
            email_field.clear()
            email_field.send_keys(email)
            pw_field = driver.find_element(By.NAME, "password")
            pw_field.clear()
            pw_field.send_keys(password)
            driver.find_element(
                By.XPATH, "//button[contains(text(),'Login')]"
            ).click()
            time.sleep(5)
            if "opportunities" in driver.current_url:
                logger.info("Instahyre login successful")
                return True
        except Exception as e:
            logger.warning(f"Instahyre auto-login failed: {e}")

    logger.warning(
        "Instahyre: Please log in manually in the browser window "
        "(Google/LinkedIn SSO). The bot will resume once logged in."
    )
    for _ in range(60):
        time.sleep(3)
        if "opportunities" in driver.current_url and "login" not in driver.current_url:
            logger.info("Instahyre login detected")
            return True

    logger.error("Instahyre login timed out")
    return False


def search_jobs(
    driver: webdriver.Chrome, keyword: str = "", location: str = "",
) -> list[dict]:
    """Load Instahyre opportunities (platform auto-recommends based on profile)."""
    url = f"{BASE_URL}/candidate/opportunities/?matching=true"
    logger.info("Loading Instahyre recommended opportunities")
    driver.get(url)
    time.sleep(5)

    _scroll_page(driver, scrolls=8)

    jobs = _extract_jobs(driver)
    logger.info(f"Found {len(jobs)} Instahyre opportunities")

    if not jobs:
        _debug_dump_page(driver)

    return jobs


def _scroll_page(driver: webdriver.Chrome, scrolls: int = 5):
    for _ in range(scrolls):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight)"
        )
        time.sleep(2)


JS_EXTRACT_JOBS = """
var buttons = document.querySelectorAll('.button-interested');
var results = [];
buttons.forEach(function(btn, idx) {
    var card = btn;
    for (var i = 0; i < 10; i++) {
        card = card.parentElement;
        if (!card) break;
        if ((card.innerText || '').indexOf('Job available in') >= 0) break;
    }
    if (!card) return;

    var lines = (card.innerText || '').split('\\n')
        .map(function(s) { return s.trim(); })
        .filter(function(s) { return s.length > 2 && s.length < 200; });
    if (lines.length < 2) return;

    var firstLine = lines[0];
    var dash = firstLine.indexOf(' - ');
    var company = dash > 0 ? firstLine.substring(0, dash).trim() : '';
    var title = dash > 0 ? firstLine.substring(dash + 3).trim() : firstLine;

    var location = '';
    for (var j = 0; j < lines.length; j++) {
        if (lines[j].toLowerCase().indexOf('job available in') === 0) {
            location = lines[j].replace(/^[Jj]ob available in\\s*/, '');
            break;
        }
    }

    if (title && title.indexOf('View') !== 0
        && title !== 'Not interested') {
        results.push({
            title: title,
            company: company,
            location: location,
            index: idx
        });
    }
});
return results;
"""


def _extract_jobs(driver: webdriver.Chrome) -> list[dict]:
    try:
        raw = driver.execute_script(JS_EXTRACT_JOBS)
    except Exception as e:
        logger.error(f"Instahyre JS extraction error: {e}")
        return []

    jobs = []
    for j in (raw or []):
        title = (j.get("title") or "").strip()
        company = (j.get("company") or "").strip()
        if not title:
            continue

        uid = hashlib.md5(
            f"{title}|{company}".encode()
        ).hexdigest()[:12]

        jobs.append({
            "title": title,
            "company": company,
            "location": j.get("location", ""),
            "description": "",
            "link": "",
            "job_id": f"instahyre_{uid}",
            "card_index": j.get("index", -1),
        })

    return jobs


JS_CLICK_INTERESTED = """
var idx = arguments[0];
var buttons = document.querySelectorAll('.button-interested');
if (idx >= 0 && idx < buttons.length) {
    buttons[idx].click();
    return {clicked: true};
}
return {clicked: false, total_buttons: buttons.length};
"""


def apply_to_job(driver: webdriver.Chrome, job: dict) -> bool:
    title = job.get("title", "")
    card_index = job.get("card_index", -1)

    try:
        result = driver.execute_script(JS_CLICK_INTERESTED, card_index)

        if result and result.get("clicked"):
            logger.info(f"Applied: {title} at {job.get('company', '')}")
            time.sleep(2)
            _handle_post_apply(driver)
            return True

        logger.warning(
            f"Could not click View/Interested for: {title} "
            f"(buttons: {result.get('total_buttons', 0) if result else 0})"
        )
        return False

    except Exception as e:
        logger.error(f"Error applying to {title}: {e}")
        return False


def _handle_post_apply(driver: webdriver.Chrome):
    """Handle any post-click modal (questionnaire, confirmation)."""
    try:
        modal_sels = [
            "[class*='modal']", "[role='dialog']",
            "[class*='popup']", "[class*='overlay']",
        ]
        for sel in modal_sels:
            try:
                modal = driver.find_element(By.CSS_SELECTOR, sel)
                if not modal.is_displayed():
                    continue

                for xpath in [
                    "//button[contains(text(),'Submit')]",
                    "//button[contains(text(),'Done')]",
                    "//button[contains(text(),'OK')]",
                    "//button[contains(text(),'Close')]",
                    "//button[contains(text(),'Continue')]",
                ]:
                    try:
                        btn = driver.find_element(By.XPATH, xpath)
                        if btn.is_displayed():
                            driver.execute_script(
                                "arguments[0].click();", btn
                            )
                            time.sleep(1)
                            return
                    except NoSuchElementException:
                        continue
            except NoSuchElementException:
                continue
    except Exception:
        pass


def _debug_dump_page(driver: webdriver.Chrome):
    """Log page structure when extraction finds nothing."""
    try:
        info = driver.execute_script("""
            var url = window.location.href;
            var title = document.title;
            var btns = Array.from(document.querySelectorAll('button'))
                .filter(function(b) { return b.offsetHeight > 0; })
                .map(function(b) { return b.textContent.trim().substring(0,60); })
                .filter(function(t) { return t.length > 0; });
            var links = Array.from(document.querySelectorAll('a[href]'))
                .filter(function(a) { return a.offsetHeight > 0; })
                .slice(0, 20)
                .map(function(a) {
                    return {text: a.textContent.trim().substring(0,60),
                            href: a.getAttribute('href')};
                });
            var bodyText = document.body.innerText.substring(0, 800);
            return {url: url, title: title, buttons: btns.slice(0, 20),
                    links: links, bodyPreview: bodyText};
        """)

        logger.warning(
            f"INSTAHYRE DEBUG - URL: {info.get('url')}\n"
            f"  Page title: {info.get('title')}\n"
            f"  Buttons: {info.get('buttons')}\n"
            f"  Links: {[l.get('text') for l in info.get('links', [])]}\n"
            f"  Body preview: {info.get('bodyPreview', '')[:300]}"
        )
    except Exception as e:
        logger.warning(f"INSTAHYRE DEBUG dump failed: {e}")
