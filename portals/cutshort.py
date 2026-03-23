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
    """Browse Cutshort job listings with fallback URL strategies."""
    slug = keyword or "backend-developer"
    slug = slug.lower().replace(" ", "-")

    category_url = f"{BASE_URL}/jobs/{slug}-jobs"
    search_url = f"{BASE_URL}/jobs?search={slug.replace('-', '+')}"

    logger.info(f"Searching Cutshort: {slug}")
    driver.get(category_url)
    time.sleep(6)

    _scroll_page(driver, scrolls=14)
    jobs = _extract_jobs(driver)

    if not jobs:
        logger.info(f"Category page empty, trying search URL for: {slug}")
        driver.get(search_url)
        time.sleep(6)
        _scroll_page(driver, scrolls=14)
        jobs = _extract_jobs(driver)

    logger.info(f"Found {len(jobs)} Cutshort jobs for '{slug}'")

    if not jobs:
        _debug_dump_page(driver)

    return jobs


def _scroll_page(driver: webdriver.Chrome, scrolls: int = 14):
    last_height = 0
    for _ in range(scrolls):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight)"
        )
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


JS_EXTRACT_JOBS = """
var results = [];

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
    var link = '';

    for (var j = 0; j < lines.length; j++) {
        if (lines[j].startsWith('at ')) {
            company = lines[j].substring(3).trim();
            break;
        }
    }
    if (!company && lines.length > 1) company = lines[1];

    // Extract link from any anchor in the card
    var anchors = card.querySelectorAll('a[href]');
    for (var a = 0; a < anchors.length; a++) {
        var href = anchors[a].getAttribute('href') || '';
        if (href.includes('/job/') || href.includes('/jobs/')) {
            link = href.startsWith('http') ? href : 'https://cutshort.io' + href;
            break;
        }
    }

    var cities = ['bangalore','bengaluru','noida','gurgaon','gurugram',
                  'hyderabad','mumbai','pune','chennai','delhi',
                  'remote','india','work from home','wfh'];
    for (var k = 0; k < lines.length; k++) {
        var lower = lines[k].toLowerCase();
        for (var c = 0; c < cities.length; c++) {
            if (lower.includes(cities[c])) { location = lines[k]; break; }
        }
        if (location) break;
    }

    // Fallback: scan card's full text for city mentions
    if (!location) {
        var cardText = (card.innerText || '').toLowerCase();
        for (var c2 = 0; c2 < cities.length; c2++) {
            if (cardText.includes(cities[c2])) {
                location = cities[c2].charAt(0).toUpperCase() + cities[c2].slice(1);
                break;
            }
        }
    }

    if (title) {
        results.push({
            title: title, company: company,
            location: location, link: link, index: idx
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

# Prefer this over card_index: after each apply the DOM changes and indices shift.
JS_CLICK_APPLY_BY_CARD = """
var titleNeedle = (arguments[0] || '').toLowerCase().trim();
var companyNeedle = (arguments[1] || '').toLowerCase().trim();
if (!titleNeedle) return {clicked: false, reason: 'no_title'};

var allEls = Array.from(document.querySelectorAll('button, a'));
var applyBtns = allEls.filter(function(b) {
    var t = (b.textContent || '').trim().toLowerCase();
    return t === 'apply now' || t === 'apply'
           || t === 'interested' || t === 'connect';
});

for (var i = 0; i < applyBtns.length; i++) {
    var btn = applyBtns[i];
    var card = btn;
    for (var j = 0; j < 14; j++) {
        card = card.parentElement;
        if (!card) break;
        var h = card.getBoundingClientRect().height;
        if (h > 100) break;
    }
    if (!card) continue;
    var cardText = (card.innerText || '').toLowerCase();
    if (cardText.indexOf(titleNeedle) === -1) continue;
    if (companyNeedle && cardText.indexOf(companyNeedle) === -1) continue;
    btn.click();
    return {clicked: true, matched: i};
}
return {clicked: false, total: applyBtns.length, reason: 'no_match'};
"""


def _extract_jobs(driver: webdriver.Chrome) -> list[dict]:
    try:
        raw = driver.execute_script(JS_EXTRACT_JOBS)
    except Exception as e:
        logger.error(f"Cutshort JS extraction error: {e}")
        return []

    jobs = []
    seen = set()
    for j in (raw or []):
        title = (j.get("title") or "").strip()
        company = (j.get("company") or "").strip()
        if not title:
            continue
        dedup_key = f"{title}|{company}".lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        uid = hashlib.md5(dedup_key.encode()).hexdigest()[:12]
        jobs.append({
            "title": title,
            "company": company,
            "location": j.get("location", ""),
            "description": "",
            "link": j.get("link", ""),
            "job_id": f"cutshort_{uid}",
            "card_index": j.get("index", -1),
        })
    return jobs


def apply_to_job(driver: webdriver.Chrome, job: dict) -> bool:
    title = job.get("title", "")
    company = job.get("company", "") or ""
    card_index = job.get("card_index", -1)

    try:
        # 1) Stable: find Apply on the card that contains this title (and company).
        #    Using card_index breaks after earlier applies change the DOM order.
        t_needle = (title or "").strip().lower()[:120]
        c_needle = (company or "").strip().lower()[:100]
        result = None
        if t_needle:
            result = driver.execute_script(
                JS_CLICK_APPLY_BY_CARD, t_needle, c_needle
            )
        if not (result and result.get("clicked")) and c_needle:
            result = driver.execute_script(JS_CLICK_APPLY_BY_CARD, t_needle, "")

        # 2) Open job URL if listing page did not match (card off-screen, etc.)
        opened_detail = False
        if not (result and result.get("clicked")):
            link = (job.get("link") or "").strip()
            if link:
                opened_detail = True
                driver.get(link)
                time.sleep(4)
                result = driver.execute_script(
                    JS_CLICK_APPLY_BY_CARD, t_needle, c_needle
                )

        # 3) Last resort: index only while still on listing (index is wrong on detail page)
        if not (result and result.get("clicked")) and not opened_detail:
            result = driver.execute_script(JS_CLICK_APPLY, card_index)

        def _return_to_listing():
            if not opened_detail:
                return
            try:
                driver.back()
                time.sleep(3)
            except Exception:
                pass

        if result and result.get("clicked"):
            logger.info(f"Applied: {title} at {company}")
            time.sleep(2)
            _handle_post_apply(driver)
            _return_to_listing()
            return True

        _return_to_listing()

        logger.warning(
            f"Could not click Apply for: {title} "
            f"(buttons: {result.get('total', 0) if result else 0}, "
            f"reason: {result.get('reason', 'index') if result else 'none'})"
        )
        return False
    except Exception as e:
        logger.error(f"Error applying to {title}: {e}")
        return False


def _handle_post_apply(driver: webdriver.Chrome):
    for _ in range(3):
        clicked = False
        for xpath in [
            "//button[contains(text(),'Submit')]",
            "//button[contains(text(),'Done')]",
            "//button[contains(text(),'Continue')]",
            "//button[contains(text(),'Close')]",
            "//button[contains(text(),'OK')]",
            "//button[contains(text(),'Skip')]",
            "//button[@aria-label='Close']",
            "//div[@role='dialog']//button[last()]",
            "//*[contains(@class,'close') or contains(@class,'dismiss')]",
        ]:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    clicked = True
                    break
            except NoSuchElementException:
                continue
            except Exception:
                continue
        if not clicked:
            break


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
