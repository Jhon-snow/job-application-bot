import time
import hashlib
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

logger = logging.getLogger(__name__)

BASE_URL = "https://cutshort.io"


def check_already_logged_in(driver: webdriver.Chrome) -> bool:
    driver.get(f"{BASE_URL}/dashboard")
    time.sleep(5)
    url = driver.current_url
    if "login" in url or "signup" in url or "register" in url:
        return False
    return "cutshort.io" in url and "login" not in url


def login(driver: webdriver.Chrome, email: str = "", password: str = "") -> bool:
    driver.get(f"{BASE_URL}/login")
    time.sleep(3)
    logger.warning(
        "Cutshort: Please log in manually in the browser "
        "(Google/LinkedIn SSO). The bot will resume once logged in."
    )
    for _ in range(60):
        time.sleep(3)
        url = driver.current_url
        if "login" not in url and "signup" not in url and "register" not in url:
            logger.info("Cutshort login detected")
            return True
    logger.error("Cutshort login timed out")
    return False


def search_jobs(
    driver: webdriver.Chrome, keyword: str = "", location: str = "",
) -> list[dict]:
    """Browse Cutshort job listings."""
    slug = keyword or "backend-developer"
    slug = slug.lower().replace(" ", "-")
    url = f"{BASE_URL}/jobs/{slug}-jobs"
    logger.info(f"Searching Cutshort: {slug}")
    driver.get(url)
    time.sleep(6)

    _scroll_page(driver, scrolls=5)

    jobs = _extract_jobs(driver)
    logger.info(f"Found {len(jobs)} Cutshort jobs")

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
var results = [];

// Cutshort: Find "Apply now" links/buttons and walk up to job cards
var allEls = Array.from(document.querySelectorAll('button, a'));
var applyBtns = allEls.filter(function(b) {
    var t = (b.textContent || '').trim().toLowerCase();
    return t === 'apply now' || t === 'apply'
           || t === 'interested' || t === 'connect';
});

applyBtns.forEach(function(btn, idx) {
    var card = btn;
    for (var i = 0; i < 12; i++) {
        card = card.parentElement;
        if (!card) break;
        var h = card.getBoundingClientRect().height;
        if (h > 120) break;
    }
    if (!card) return;

    var lines = (card.innerText || '').split('\\n')
        .map(function(s) { return s.trim(); })
        .filter(function(s) {
            return s.length > 2 && s.length < 200
                && s.toLowerCase() !== 'apply now'
                && s.toLowerCase() !== 'apply'
                && !s.startsWith('Posted by');
        });
    if (lines.length < 2) return;

    var title = lines[0] || '';
    var company = '';
    var location = '';

    // Look for "at CompanyName" pattern
    for (var j = 0; j < lines.length; j++) {
        if (lines[j].startsWith('at ')) {
            company = lines[j].substring(3).trim();
            break;
        }
    }
    if (!company && lines.length > 1) company = lines[1];

    var cities = ['bangalore','bengaluru','noida','gurgaon','gurugram',
                  'hyderabad','mumbai','pune','chennai','delhi',
                  'remote','india','work from home'];
    for (var k = 0; k < lines.length; k++) {
        var lower = lines[k].toLowerCase();
        for (var c = 0; c < cities.length; c++) {
            if (lower.includes(cities[c])) { location = lines[k]; break; }
        }
        if (location) break;
    }

    if (title) {
        results.push({
            title: title, company: company,
            location: location, index: idx
        });
    }
});

return results;
"""

JS_CLICK_APPLY = """
var idx = arguments[0];
var allEls = Array.from(document.querySelectorAll('button, a'));
var applyBtns = allEls.filter(function(b) {
    var t = (b.textContent || '').trim().toLowerCase();
    return t === 'apply now' || t === 'apply'
           || t === 'interested' || t === 'connect';
});
if (idx >= 0 && idx < applyBtns.length) {
    applyBtns[idx].click();
    return {clicked: true};
}
return {clicked: false, total: applyBtns.length};
"""


def _extract_jobs(driver: webdriver.Chrome) -> list[dict]:
    try:
        raw = driver.execute_script(JS_EXTRACT_JOBS)
    except Exception as e:
        logger.error(f"Cutshort JS extraction error: {e}")
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
            "job_id": f"cutshort_{uid}",
            "card_index": j.get("index", -1),
        })
    return jobs


def apply_to_job(driver: webdriver.Chrome, job: dict) -> bool:
    title = job.get("title", "")
    card_index = job.get("card_index", -1)

    try:
        result = driver.execute_script(JS_CLICK_APPLY, card_index)
        if result and result.get("clicked"):
            logger.info(f"Applied: {title} at {job.get('company', '')}")
            time.sleep(2)
            _handle_post_apply(driver)
            return True

        logger.warning(
            f"Could not click Apply for: {title} "
            f"(buttons: {result.get('total', 0) if result else 0})"
        )
        return False
    except Exception as e:
        logger.error(f"Error applying to {title}: {e}")
        return False


def _handle_post_apply(driver: webdriver.Chrome):
    try:
        for xpath in [
            "//button[contains(text(),'Submit')]",
            "//button[contains(text(),'Done')]",
            "//button[contains(text(),'Close')]",
            "//button[contains(text(),'OK')]",
            "//button[@aria-label='Close']",
        ]:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    return
            except NoSuchElementException:
                continue
    except Exception:
        pass


def _debug_dump_page(driver: webdriver.Chrome):
    try:
        info = driver.execute_script("""
            var url = window.location.href;
            var title = document.title;
            var btns = Array.from(document.querySelectorAll('button, a'))
                .filter(function(b) { return b.offsetHeight > 0; })
                .map(function(b) {
                    return {text: b.textContent.trim().substring(0,80),
                            tag: b.tagName, cls: b.className.substring(0,80)};
                })
                .filter(function(b) { return b.text.length > 0; })
                .slice(0, 30);
            var bodyText = document.body.innerText.substring(0, 1500);
            return {url: url, title: title, buttons: btns,
                    bodyPreview: bodyText};
        """)
        logger.warning(
            f"CUTSHORT DEBUG - URL: {info.get('url')}\n"
            f"  Title: {info.get('title')}\n"
            f"  Buttons: {[b.get('text','')[:40] for b in info.get('buttons',[])]}\n"
            f"  Body: {info.get('bodyPreview','')[:500]}"
        )
    except Exception as e:
        logger.warning(f"CUTSHORT DEBUG dump failed: {e}")
