import os as _os
import time
import logging
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)

logger = logging.getLogger(__name__)


def check_already_logged_in(driver: webdriver.Chrome) -> bool:
    """Navigate to LinkedIn feed and check if the session is already active."""
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(4)
    url = driver.current_url
    if "feed" in url or "mynetwork" in url or "jobs" in url:
        return True
    return False


def login(driver: webdriver.Chrome, email: str, password: str) -> bool:
    logger.info("Logging into LinkedIn...")
    driver.get("https://www.linkedin.com/login")
    time.sleep(3)

    try:
        driver.find_element(By.ID, "username").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(5)

        if "feed" in driver.current_url or "mynetwork" in driver.current_url:
            logger.info("LinkedIn login successful")
            return True

        if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            logger.warning(
                "LinkedIn requires verification. Complete it manually in the browser."
            )
            input("Press Enter after completing verification...")
            return True

        logger.error(f"Login may have failed. Current URL: {driver.current_url}")
        return False

    except Exception as e:
        logger.error(f"LinkedIn login failed: {e}")
        return False


def search_jobs(driver: webdriver.Chrome, keyword: str, location: str = "") -> list[dict]:
    encoded_keyword = quote_plus(keyword)
    encoded_location = quote_plus(location) if location else ""

    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={encoded_keyword}"
        f"&location={encoded_location}"
        f"&f_AL=true"
        f"&f_E=4"
        f"&sortBy=DD"
    )

    logger.info(f"Searching LinkedIn: {keyword} in {location or 'any location'}")
    driver.get(url)
    time.sleep(5)

    _scroll_job_list(driver)

    jobs = []
    job_cards = driver.find_elements(By.CSS_SELECTOR, ".job-card-container")
    logger.info(f"Found {len(job_cards)} job cards")

    for card in job_cards:
        try:
            job = _extract_job_card(card)
            if job:
                jobs.append(job)
        except Exception as e:
            logger.debug(f"Failed to extract job card: {e}")

    return jobs


def _scroll_job_list(driver: webdriver.Chrome, scrolls: int = 6):
    scroll_selectors = [
        ".jobs-search-results-list",
        ".scaffold-layout__list > div",
        ".scaffold-layout__list",
    ]
    for _ in range(scrolls):
        scrolled = False
        for sel in scroll_selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight", el
                )
                scrolled = True
                break
            except NoSuchElementException:
                continue
        if not scrolled:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)


JS_EXTRACT_CARD = """
var card = arguments[0];
var titleLink = card.querySelector('a[href*="/jobs/view/"]');
if (!titleLink) return null;
var title = titleLink.innerText.split('\\n')[0].trim();

var subtitle = card.querySelector('.artdeco-entity-lockup__subtitle');
var company = subtitle ? subtitle.innerText.split('\\n')[0].trim() : '';

var caption = card.querySelector('.artdeco-entity-lockup__caption');
var location = caption ? caption.innerText.split('\\n')[0].trim() : '';

var jobId = card.getAttribute('data-job-id') || '';
var link = titleLink.href || '';
if (!jobId) {
    var m = link.match(/\\/jobs\\/view\\/(\\d+)/);
    if (m) jobId = m[1];
}
return {title: title, company: company, location: location, jobId: jobId, link: link};
"""


def _extract_job_card(card) -> dict | None:
    try:
        driver = card.parent
        data = driver.execute_script(JS_EXTRACT_CARD, card)
        if not data or not data.get("title"):
            return None

        job_id = data["jobId"]
        link = data.get("link", "")
        if not link and job_id:
            link = f"https://www.linkedin.com/jobs/view/{job_id}/"

        return {
            "title": data["title"],
            "company": data["company"],
            "location": data["location"],
            "description": "",
            "link": link,
            "job_id": f"linkedin_{job_id}",
        }
    except Exception:
        return None


def apply_to_job(driver: webdriver.Chrome, job: dict) -> bool:
    """Navigate to job in search context, click Easy Apply from side panel."""
    link = job.get("link", "")
    job_id_raw = job.get("job_id", "").replace("linkedin_", "")

    if not link and job_id_raw:
        link = f"https://www.linkedin.com/jobs/view/{job_id_raw}/"

    if job_id_raw:
        current = driver.current_url
        if "/jobs/search/" in current and "currentJobId" not in current:
            sep = "&" if "?" in current else "?"
            driver.get(f"{current}{sep}currentJobId={job_id_raw}")
        elif "/jobs/search/" in current:
            import re as _re
            new_url = _re.sub(r"currentJobId=\d+", f"currentJobId={job_id_raw}", current)
            driver.get(new_url)
        else:
            driver.get(link)
    elif link:
        driver.get(link)
    else:
        logger.warning(f"No link for: {job['title']}")
        return False

    try:
        time.sleep(4)

        description = _get_job_description(driver)
        job["description"] = description

        apply_button = _find_easy_apply_button(driver)
        if not apply_button:
            logger.info(f"No Easy Apply for: {job['title']} at {job['company']}")
            return False

        try:
            apply_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", apply_button)
        time.sleep(2)

        return _complete_application(driver, job)

    except Exception as e:
        logger.error(f"Error applying to {job['title']}: {e}")
        return False


def _get_job_description(driver: webdriver.Chrome) -> str:
    for sel in [".jobs-description__content", ".jobs-box__html-content"]:
        try:
            return driver.find_element(By.CSS_SELECTOR, sel).text
        except NoSuchElementException:
            continue
    return ""


def _find_easy_apply_button(driver: webdriver.Chrome):
    xpaths = [
        "//button[contains(@class,'jobs-apply-button')]",
        "//button[contains(text(),'Easy Apply')]",
        "//button[contains(@aria-label,'Easy Apply')]",
        "//button[.//span[contains(text(),'Easy Apply')]]",
    ]
    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for btn in elements:
                if btn.is_displayed() and btn.is_enabled():
                    return btn
        except Exception:
            continue

    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = (btn.text or "").strip().lower()
            if "easy apply" in text and btn.is_displayed():
                return btn
    except Exception:
        pass

    return None


def _complete_application(driver: webdriver.Chrome, job: dict) -> bool:
    max_steps = 10
    for step in range(max_steps):
        time.sleep(2)

        _fill_form_fields(driver)

        if _click_modal_button(driver, "Submit application"):
            logger.info(f"Applied: {job['title']} at {job['company']}")
            time.sleep(1)
            _dismiss_post_apply(driver)
            return True

        for label in ("Next", "Review", "Continue"):
            if _click_modal_button(driver, label):
                logger.debug(f"Step {step}: clicked {label}")
                break
        else:
            unfilled = _count_unfilled_required(driver)
            if unfilled > 0:
                logger.debug(
                    f"Step {step}: {unfilled} required field(s) still empty, "
                    "retrying with fallback fill"
                )
                _fill_remaining_required(driver)
                time.sleep(1)

                if _click_modal_button(driver, "Submit application"):
                    logger.info(f"Applied: {job['title']} at {job['company']}")
                    time.sleep(1)
                    _dismiss_post_apply(driver)
                    return True
                for label in ("Next", "Review", "Continue"):
                    if _click_modal_button(driver, label):
                        break
                else:
                    _log_form_state(driver, job.get("title", ""))
                    _dismiss_modal(driver)
                    return False
            elif not _is_modal_visible(driver):
                break

    logger.warning(f"Could not complete application for: {job['title']}")
    _dismiss_modal(driver)
    return False


def _is_modal_visible(driver: webdriver.Chrome) -> bool:
    for sel in [".jobs-easy-apply-modal", ".artdeco-modal", "[role='dialog']"]:
        try:
            m = driver.find_element(By.CSS_SELECTOR, sel)
            if m.is_displayed():
                return True
        except NoSuchElementException:
            continue
    return False


def _fill_form_fields(driver: webdriver.Chrome):
    _select_resume(driver)
    _fill_empty_inputs(driver)
    _fill_textareas(driver)
    _fill_dropdowns(driver)
    _fill_radio_buttons(driver)
    _fill_checkboxes(driver)


def _select_resume(driver: webdriver.Chrome):
    try:
        resume_items = driver.find_elements(
            By.CSS_SELECTOR,
            "div[data-test-document-resume-card], "
            ".jobs-document-upload-redesign-card, "
            ".ui-attachment--pdf",
        )
        for item in resume_items:
            if item.is_displayed():
                driver.execute_script("arguments[0].click();", item)
                logger.debug("Selected resume")
                return
    except Exception:
        pass

    try:
        labels = driver.find_elements(
            By.XPATH,
            "//label[contains(@class,'document') or contains(@for,'resume')]",
        )
        for label in labels:
            if label.is_displayed():
                driver.execute_script("arguments[0].click();", label)
                logger.debug("Clicked resume label")
                return
    except Exception:
        pass


def _select_preferred_email(driver: webdriver.Chrome):
    import config
    preferred = config.PREFERRED_EMAIL.lower()

    try:
        selects = driver.find_elements(By.TAG_NAME, "select")
        for sel in selects:
            if not sel.is_displayed():
                continue
            label_text = _get_input_label(driver, sel).lower()
            if "email" not in label_text:
                continue
            options = sel.find_elements(By.TAG_NAME, "option")
            for opt in options:
                opt_text = (opt.text.strip().lower()
                            or opt.get_attribute("value") or "")
                if preferred in opt_text.lower():
                    opt.click()
                    logger.debug(f"Selected email: {config.PREFERRED_EMAIL}")
                    return
    except Exception:
        pass


def _match_field_value(label: str) -> str | None:
    """Match a field label to a default value. Returns None if no match."""
    import config

    if "email" in label:
        return config.PREFERRED_EMAIL
    if any(k in label for k in ("phone", "mobile", "contact number")):
        return config.PHONE_NUMBER

    if ("current" in label and
            any(k in label for k in ("ctc", "salary", "compensation",
                                     "lpa", "annual", "package"))):
        return str(config.CURRENT_CTC_LAKHS)
    if (any(k in label for k in ("expected", "desired")) and
            any(k in label for k in ("ctc", "salary", "compensation",
                                     "lpa", "annual", "package"))):
        return str(config.EXPECTED_CTC_LAKHS)
    if any(k in label for k in ("ctc", "salary", "compensation", "lpa",
                                "package", "remuneration")):
        return str(config.CURRENT_CTC_LAKHS)

    if any(k in label for k in ("notice period", "notice", "earliest start",
                                "how soon", "joining")):
        return "30"

    if ("experience" in label or "years of work" in label or
            "how many year" in label or "professional experience" in label):
        return str(config.TOTAL_EXPERIENCE_YEARS)

    if any(k in label for k in ("city", "preferred location",
                                "location preference")):
        return config.PREFERRED_CITY

    if "linkedin" in label:
        return config.LINKEDIN_PROFILE_URL or None
    if "github" in label:
        return config.GITHUB_URL or None
    if any(k in label for k in ("portfolio", "website", "personal url",
                                "personal link")):
        return config.GITHUB_URL or None

    if any(k in label for k in ("graduation", "passing year", "batch",
                                "year of completion", "year of passing")):
        return config.GRADUATION_YEAR
    if any(k in label for k in ("gpa", "cgpa")):
        return "8.0"
    if "percentage" in label:
        return "80"
    if "degree" in label:
        return "B.Tech"
    if any(k in label for k in ("university", "college", "school",
                                "institution")):
        return config.COLLEGE or None

    if any(k in label for k in ("authorized", "authorised", "legally",
                                "legal right", "eligible to work",
                                "right to work")):
        return "Yes"
    if any(k in label for k in ("sponsorship", "visa")):
        return "No"
    if any(k in label for k in ("relocate", "commute", "willing to",
                                "open to", "comfortable")):
        return "Yes"
    if any(k in label for k in ("gender",)):
        return "Male"
    if any(k in label for k in ("race", "ethnicity")):
        return "Decline"
    if any(k in label for k in ("disability", "veteran", "handicap")):
        return "No"
    if "headline" in label:
        return config.HEADLINE

    if "year" in label:
        return str(config.TOTAL_EXPERIENCE_YEARS)
    if "how many" in label:
        return str(config.TOTAL_EXPERIENCE_YEARS)
    if "proficien" in label:
        return str(config.TOTAL_EXPERIENCE_YEARS)

    return None


def _fill_empty_inputs(driver: webdriver.Chrome):
    """Fill text/tel/email/number inputs using pattern matching + fallback."""
    _select_preferred_email(driver)

    try:
        modal = driver.find_element(
            By.CSS_SELECTOR,
            ".jobs-easy-apply-modal, .artdeco-modal, [role='dialog']",
        )
    except NoSuchElementException:
        return

    input_sel = (
        "input[type='text'], input[type='tel'], "
        "input[type='email'], input[type='number']"
    )
    inputs = modal.find_elements(By.CSS_SELECTOR, input_sel)
    for inp in inputs:
        try:
            if not inp.is_displayed():
                continue
            val = (inp.get_attribute("value") or "").strip()
            if val:
                continue

            label_text = _get_input_label(driver, inp).lower()
            matched_value = _match_field_value(label_text)

            if matched_value:
                inp.clear()
                inp.send_keys(str(matched_value))
                logger.debug(f"Filled '{label_text[:60]}' → '{matched_value}'")
            else:
                inp_type = inp.get_attribute("type") or "text"
                fallback = (str(__import__('config').TOTAL_EXPERIENCE_YEARS)
                            if inp_type == "number" else "Yes")
                inp.clear()
                inp.send_keys(fallback)
                logger.warning(
                    f"UNKNOWN_FIELD input '{label_text[:80]}' "
                    f"(type={inp_type}) → '{fallback}'"
                )
                _track_unknown_field(label_text, inp_type, fallback)
        except Exception:
            continue


def _fill_textareas(driver: webdriver.Chrome):
    """Fill empty textareas (cover letter, additional info, etc.)."""
    try:
        modal = driver.find_element(
            By.CSS_SELECTOR,
            ".jobs-easy-apply-modal, .artdeco-modal, [role='dialog']",
        )
    except NoSuchElementException:
        return

    for ta in modal.find_elements(By.TAG_NAME, "textarea"):
        try:
            if not ta.is_displayed():
                continue
            if (ta.get_attribute("value") or "").strip():
                continue
            label_text = _get_input_label(ta.parent, ta).lower()
            if any(k in label_text for k in ("cover", "letter", "why",
                                             "about you", "tell us",
                                             "additional")):
                ta.send_keys(
                    "I am a Senior Backend Engineer with 6+ years of "
                    "experience in scalable distributed systems, "
                    "microservices, and API design. I am excited about "
                    "this opportunity."
                )
            else:
                ta.send_keys("N/A")
            logger.debug(f"Filled textarea: '{label_text[:60]}'")
        except Exception:
            continue


def _fill_checkboxes(driver: webdriver.Chrome):
    """Check all unchecked visible checkboxes (terms, acknowledgments)."""
    try:
        modal = driver.find_element(
            By.CSS_SELECTOR,
            ".jobs-easy-apply-modal, .artdeco-modal, [role='dialog']",
        )
    except NoSuchElementException:
        return

    for cb in modal.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        try:
            if cb.is_displayed() and not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
                logger.debug("Checked checkbox")
        except Exception:
            continue


def _get_input_label(driver: webdriver.Chrome, inp) -> str:
    inp_id = inp.get_attribute("id") or ""
    if inp_id:
        try:
            label = driver.find_element(
                By.CSS_SELECTOR, f"label[for='{inp_id}']"
            )
            return label.text
        except NoSuchElementException:
            pass

    try:
        parent = inp.find_element(By.XPATH, "./..")
        return parent.text
    except Exception:
        pass

    aria_label = inp.get_attribute("aria-label") or ""
    placeholder = inp.get_attribute("placeholder") or ""
    return aria_label or placeholder


_YES_PATTERNS = frozenset((
    "authorized", "authorised", "legally", "eligible",
    "relocate", "commute", "willing", "comfortable",
    "background check", "drug test", "18 years",
    "right to work", "open to",
))

_NO_PATTERNS = frozenset((
    "sponsorship", "visa", "disability", "veteran", "handicap",
))


def _pick_yes_no(label: str) -> str | None:
    """Decide Yes/No based on common patterns. Returns None if ambiguous."""
    ll = label.lower()
    if any(p in ll for p in _NO_PATTERNS):
        return "No"
    if any(p in ll for p in _YES_PATTERNS):
        return "Yes"
    return None


def _fill_dropdowns(driver: webdriver.Chrome):
    """Smart dropdown filler: prefers Yes/No match, then first valid option."""
    try:
        selects = driver.find_elements(By.CSS_SELECTOR, "select")
        for sel in selects:
            try:
                if not sel.is_displayed():
                    continue
                current = sel.get_attribute("value") or ""
                if current:
                    continue

                label_text = _get_input_label(driver, sel).lower()
                options = sel.find_elements(By.TAG_NAME, "option")

                yn = _pick_yes_no(label_text)
                if yn:
                    for opt in options:
                        if opt.text.strip().lower() == yn.lower():
                            opt.click()
                            logger.debug(
                                f"Dropdown '{label_text[:50]}' → '{yn}'"
                            )
                            break
                    else:
                        _select_first_valid_option(options)
                else:
                    _select_first_valid_option(options)
            except Exception:
                continue
    except Exception:
        pass


def _select_first_valid_option(options):
    for opt in options:
        val = opt.get_attribute("value") or ""
        text = opt.text.strip()
        if val and text and text.lower() not in ("select an option",
                                                  "select", "-- select --",
                                                  "choose"):
            opt.click()
            break


def _fill_radio_buttons(driver: webdriver.Chrome):
    """Select radio buttons: prefer Yes/No match, then first option."""
    try:
        fieldsets = driver.find_elements(By.CSS_SELECTOR, "fieldset")
        for fs in fieldsets:
            try:
                radios = fs.find_elements(
                    By.CSS_SELECTOR, "input[type='radio']"
                )
                if not radios:
                    continue
                if any(r.get_attribute("checked") for r in radios):
                    continue

                label_text = fs.text.lower()
                yn = _pick_yes_no(label_text)

                if yn:
                    for i, r in enumerate(radios):
                        r_label = _get_input_label(driver, r).lower().strip()
                        if r_label == yn.lower():
                            driver.execute_script(
                                "arguments[0].click();", radios[i]
                            )
                            break
                    else:
                        driver.execute_script(
                            "arguments[0].click();", radios[0]
                        )
                else:
                    target_idx = 0
                    lines = [l.strip() for l in label_text.split("\n")]
                    if "yes" in lines:
                        for i, r in enumerate(radios):
                            rl = _get_input_label(driver, r).lower()
                            if "yes" in rl:
                                target_idx = i
                                break
                    driver.execute_script(
                        "arguments[0].click();", radios[target_idx]
                    )
            except Exception:
                continue
    except Exception:
        pass


def _fill_remaining_required(driver: webdriver.Chrome):
    """Last-resort: fill ANY remaining empty required fields with fallback."""
    import config

    try:
        modal = driver.find_element(
            By.CSS_SELECTOR,
            ".jobs-easy-apply-modal, .artdeco-modal, [role='dialog']",
        )
    except NoSuchElementException:
        return

    for inp in modal.find_elements(By.CSS_SELECTOR, "[required]"):
        try:
            if not inp.is_displayed():
                continue
            tag = inp.tag_name.lower()
            val = (inp.get_attribute("value") or "").strip()
            if val:
                continue

            label_text = _get_input_label(driver, inp).lower()
            inp_type = inp.get_attribute("type") or "text"

            if tag == "select":
                options = inp.find_elements(By.TAG_NAME, "option")
                _select_first_valid_option(options)
                logger.warning(
                    f"UNKNOWN_FIELD select '{label_text[:60]}' → first option"
                )
                _track_unknown_field(label_text, "select", "first option")
                continue

            if tag == "textarea":
                inp.send_keys("N/A")
                logger.warning(
                    f"UNKNOWN_FIELD textarea '{label_text[:60]}' → 'N/A'"
                )
                _track_unknown_field(label_text, "textarea", "N/A")
                continue

            if tag == "input":
                fallback = (
                    str(config.TOTAL_EXPERIENCE_YEARS)
                    if inp_type == "number" else "Yes"
                )
                inp.clear()
                inp.send_keys(fallback)
                logger.warning(
                    f"UNKNOWN_FIELD input '{label_text[:60]}' "
                    f"(type={inp_type}) → '{fallback}'"
                )
                _track_unknown_field(label_text, inp_type, fallback)
        except Exception:
            continue


def _log_form_state(driver: webdriver.Chrome, job_title: str):
    """Log all visible form fields for debugging stuck applications."""
    try:
        modal = driver.find_element(
            By.CSS_SELECTOR,
            ".jobs-easy-apply-modal, .artdeco-modal, [role='dialog']",
        )
    except NoSuchElementException:
        logger.warning(f"Form state for '{job_title}': no modal found")
        return

    fields = []
    for inp in modal.find_elements(
        By.CSS_SELECTOR,
        "input, select, textarea"
    ):
        try:
            if not inp.is_displayed():
                continue
            tag = inp.tag_name
            inp_type = inp.get_attribute("type") or ""
            val = (inp.get_attribute("value") or "").strip()
            req = "REQ" if inp.get_attribute("required") else "opt"
            label = _get_input_label(driver, inp)[:60]
            fields.append(f"  [{req}] {tag}({inp_type}) "
                          f"'{label}' = '{val[:30]}'")
        except Exception:
            continue

    buttons = []
    for btn in modal.find_elements(By.TAG_NAME, "button"):
        try:
            if btn.is_displayed():
                enabled = "ON" if btn.is_enabled() else "off"
                buttons.append(f"  [{enabled}] {btn.text.strip()[:40]}")
        except Exception:
            continue

    logger.warning(
        f"FORM_STATE for '{job_title}':\n"
        f"  Fields ({len(fields)}):\n" + "\n".join(fields) + "\n"
        f"  Buttons ({len(buttons)}):\n" + "\n".join(buttons)
    )


def _track_unknown_field(label: str, field_type: str, value_used: str):
    """Accumulate unknown fields to JSON for future improvement."""
    import json as _json
    import config

    try:
        path = config.UNKNOWN_FIELDS_PATH
        data = {}
        if _os.path.exists(path):
            with open(path, "r") as f:
                data = _json.load(f)

        key = label.strip()[:120]
        if not key:
            return
        from datetime import datetime as _dt
        today = _dt.now().strftime("%Y-%m-%d")

        if key in data:
            data[key]["count"] += 1
            data[key]["last_seen"] = today
        else:
            data[key] = {
                "type": field_type,
                "default_used": value_used,
                "count": 1,
                "first_seen": today,
                "last_seen": today,
            }

        with open(path, "w") as f:
            _json.dump(data, f, indent=2, sort_keys=True)
    except Exception:
        pass


MODAL_BUTTON_MAP = {
    "Submit application": [
        "//button[@aria-label='Submit application']",
        "//button[contains(.,'Submit application')]",
    ],
    "Review": [
        "//button[@aria-label='Review your application']",
        "//button[contains(.,'Review')]",
    ],
    "Next": [
        "//button[@aria-label='Continue to next step']",
        "//button[contains(.,'Next')]",
    ],
    "Continue": [
        "//button[contains(.,'Continue')]",
    ],
}


def _click_modal_button(driver: webdriver.Chrome, label: str) -> bool:
    xpaths = MODAL_BUTTON_MAP.get(label, [f"//button[contains(.,'{label}')]"])
    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for btn in elements:
                if btn.is_displayed() and btn.is_enabled():
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue
    return False


def _count_unfilled_required(driver: webdriver.Chrome) -> int:
    try:
        required = driver.find_elements(By.CSS_SELECTOR, "[required]")
        return sum(
            1 for f in required
            if f.is_displayed() and not (f.get_attribute("value") or "").strip()
        )
    except Exception:
        return 0


def _dismiss_post_apply(driver: webdriver.Chrome):
    """Close the 'Application sent' confirmation overlay."""
    time.sleep(1)
    for xpath in [
        "//button[@aria-label='Dismiss']",
        "//button[contains(text(),'Done')]",
        "//button[contains(text(),'Close')]",
    ]:
        try:
            btn = driver.find_element(By.XPATH, xpath)
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
                return
        except NoSuchElementException:
            continue


def _dismiss_modal(driver: webdriver.Chrome):
    """Close the Easy Apply modal and discard draft if asked."""
    try:
        WebDriverWait(driver, 3).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, ".jobs-loader")
            )
        )
    except TimeoutException:
        pass

    try:
        dismiss = driver.find_element(
            By.CSS_SELECTOR, "button[aria-label='Dismiss']"
        )
        driver.execute_script("arguments[0].click();", dismiss)
        time.sleep(1)
    except NoSuchElementException:
        return

    for xpath in [
        "//button[contains(text(),'Discard')]",
        "//button[@data-control-name='discard_application_confirm_btn']",
        "//button[contains(@data-test,'discard')]",
    ]:
        try:
            btn = driver.find_element(By.XPATH, xpath)
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
                return
        except NoSuchElementException:
            continue
