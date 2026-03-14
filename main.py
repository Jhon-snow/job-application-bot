import sys
import logging
import argparse
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

import config
from tracker import ApplicationTracker
from utils.filters import should_apply
from portals import linkedin, naukri, instahyre, wellfound, cutshort
from templates import print_referral_messages, print_recruiter_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"job_bot_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger(__name__)


def create_driver() -> webdriver.Chrome:
    options = Options()
    if config.HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    options.add_argument(f"--user-data-dir={config.BOT_CHROME_PROFILE_DIR}")
    logger.info(f"Using bot Chrome profile at: {config.BOT_CHROME_PROFILE_DIR}")

    if config.CHROME_DRIVER_PATH:
        service = Service(config.CHROME_DRIVER_PATH)
        return webdriver.Chrome(service=service, options=options)
    return webdriver.Chrome(options=options)


def _run_portal(
    portal_name: str,
    portal_config: dict,
    driver: webdriver.Chrome,
    tracker: ApplicationTracker,
    search_fn,
    apply_fn,
    relax_seniority: bool = False,
) -> int:
    """Generic loop for any portal using its own config dict."""
    keywords = portal_config["keywords"]
    locations = portal_config["locations"]
    limit = portal_config["daily_limit"]

    applied_count = 0
    seen_job_ids: set[str] = set()

    for keyword in keywords:
        if tracker.get_today_count(portal_name) >= limit:
            logger.info(f"{portal_name} daily limit ({limit}) reached")
            break

        for location in locations:
            if tracker.get_today_count(portal_name) >= limit:
                break

            try:
                jobs = search_fn(driver, keyword, location)
            except Exception as e:
                logger.warning(f"{portal_name} search error ({keyword} in {location}): {e}")
                continue

            for job in jobs:
                if tracker.get_today_count(portal_name) >= limit:
                    break

                job_id = job.get("job_id", "")
                if job_id in seen_job_ids:
                    continue
                seen_job_ids.add(job_id)

                if tracker.is_already_applied(job_id):
                    logger.debug(f"Already applied: {job_id}")
                    continue

                ok, reason = should_apply(
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    location=job.get("location", ""),
                    description=job.get("description", ""),
                    allowed_locations=locations,
                    blacklisted_companies=config.BLACKLISTED_COMPANIES,
                    min_experience=config.EXPERIENCE_MIN_YEARS,
                    search_location=location,
                    wfo_ok_cities=config.WFO_OK_CITIES,
                    relax_seniority=relax_seniority,
                )

                if not ok:
                    logger.info(f"Skipped: {reason}")
                    continue

                logger.info(
                    f"APPLYING: {job.get('title')} at {job.get('company')} "
                    f"[{job.get('location')}]"
                )
                success = apply_fn(driver, job)
                if success:
                    tracker.mark_applied(
                        job_id,
                        portal=portal_name,
                        company=job.get("company", ""),
                        title=job.get("title", ""),
                    )
                    applied_count += 1

    logger.info(f"{portal_name}: Applied to {applied_count} jobs")
    return applied_count


def run_linkedin(driver: webdriver.Chrome, tracker: ApplicationTracker) -> int:
    logger.info("Starting LinkedIn automation...")

    if linkedin.check_already_logged_in(driver):
        logger.info("LinkedIn: Already logged in (saved session)")
    else:
        logger.info("LinkedIn: Not logged in — attempting login...")
        if not linkedin.login(driver, config.EMAIL, config.PASSWORD):
            logger.error("LinkedIn login failed, skipping")
            return 0

    return _run_portal(
        "linkedin", config.LINKEDIN, driver, tracker,
        linkedin.search_jobs, linkedin.apply_to_job,
        relax_seniority=True,
    )


def run_naukri(driver: webdriver.Chrome, tracker: ApplicationTracker) -> int:
    logger.info("Starting Naukri automation...")

    if naukri.check_already_logged_in(driver):
        logger.info("Naukri: Already logged in (saved session)")
    else:
        logger.info("Naukri: Not logged in — attempting login...")
        if not naukri.login(driver, config.NAUKRI_EMAIL, config.NAUKRI_PASSWORD):
            logger.error("Naukri login failed, skipping")
            return 0

    return _run_portal(
        "naukri", config.NAUKRI, driver, tracker,
        naukri.search_jobs, naukri.apply_to_job,
    )


def run_instahyre(driver: webdriver.Chrome, tracker: ApplicationTracker) -> int:
    logger.info("Starting Instahyre automation...")

    if instahyre.check_already_logged_in(driver):
        logger.info("Instahyre: Already logged in (saved session)")
    else:
        logger.info("Instahyre: Not logged in — attempting login...")
        if not instahyre.login(driver):
            logger.error("Instahyre login failed, skipping")
            return 0

    return _run_portal(
        "instahyre", config.INSTAHYRE, driver, tracker,
        instahyre.search_jobs, instahyre.apply_to_job,
        relax_seniority=True,
    )


def run_wellfound(driver: webdriver.Chrome, tracker: ApplicationTracker) -> int:
    logger.info("Starting Wellfound automation...")

    if wellfound.check_already_logged_in(driver):
        logger.info("Wellfound: Already logged in (saved session)")
    else:
        logger.info("Wellfound: Not logged in — attempting login...")
        if not wellfound.login(driver):
            logger.error("Wellfound login failed, skipping")
            return 0

    return _run_portal(
        "wellfound", config.WELLFOUND, driver, tracker,
        wellfound.search_jobs, wellfound.apply_to_job,
        relax_seniority=True,
    )


def run_cutshort(driver: webdriver.Chrome, tracker: ApplicationTracker) -> int:
    logger.info("Starting Cutshort automation...")

    if cutshort.check_already_logged_in(driver):
        logger.info("Cutshort: Already logged in (saved session)")
    else:
        logger.info("Cutshort: Not logged in — attempting login...")
        if not cutshort.login(driver):
            logger.error("Cutshort login failed, skipping")
            return 0

    return _run_portal(
        "cutshort", config.CUTSHORT, driver, tracker,
        cutshort.search_jobs, cutshort.apply_to_job,
        relax_seniority=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Job Application Automation Bot")
    parser.add_argument(
        "--portal",
        choices=["linkedin", "naukri", "instahyre", "wellfound", "cutshort", "all"],
        default="all",
        help="Which portal to run (default: all)",
    )
    parser.add_argument(
        "--templates",
        action="store_true",
        help="Print referral/recruiter message templates and exit",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show application stats and exit",
    )
    args = parser.parse_args()

    tracker = ApplicationTracker(config.APPLIED_JOBS_PATH, config.PIPELINE_PATH)

    if args.stats:
        tracker.print_stats()
        return

    if args.templates:
        print_referral_messages(config.TARGET_COMPANIES)
        print_recruiter_message()
        return

    logger.info(f"Starting Job Bot - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    tracker.print_stats()

    driver = create_driver()
    total_applied = 0

    try:
        if args.portal in ("linkedin", "all"):
            total_applied += run_linkedin(driver, tracker)

        if args.portal in ("naukri", "all"):
            total_applied += run_naukri(driver, tracker)

        if args.portal in ("instahyre", "all"):
            total_applied += run_instahyre(driver, tracker)

        if args.portal in ("wellfound", "all"):
            total_applied += run_wellfound(driver, tracker)

        if args.portal in ("cutshort", "all"):
            total_applied += run_cutshort(driver, tracker)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        driver.quit()
        logger.info(f"Session complete. Total applied today: {total_applied}")
        tracker.print_stats()


if __name__ == "__main__":
    main()
