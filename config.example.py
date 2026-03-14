import os

# ── Credentials ──────────────────────────────────────────────────────
# Used for LinkedIn / Wellfound / Instahyre login fallback.
# Prefer environment variables; the defaults here are used if unset.
EMAIL = os.getenv("JOB_BOT_EMAIL", "your_email@example.com")
PASSWORD = os.getenv("JOB_BOT_PASSWORD", "your_password")

NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL", "your_naukri_email@example.com")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD", "your_naukri_password")

# ── Location preferences ─────────────────────────────────────────────
# Cities where you're okay with Work-From-Office roles
WFO_OK_CITIES = {
    "gurgaon", "gurugram", "noida",
    "bangalore", "bengaluru",
    "hyderabad", "secunderabad",
}

# ── Portal-specific settings ─────────────────────────────────────────

NAUKRI = {
    "keywords": [
        "Senior Backend Engineer",
        "Senior Software Engineer Backend",
        "Staff Backend Engineer",
        "Senior Python Engineer",
        "Backend Lead",
        "SDE-3 Backend",
    ],
    "locations": [
        "Noida",
        "Gurgaon",
        "Bangalore",
        "Hyderabad",
        "Remote",
    ],
    "daily_limit": 30,
}

LINKEDIN = {
    "keywords": [
        "Senior Backend Engineer",
        "Senior Software Engineer Backend",
        "Staff Backend Engineer",
        "Senior Python Engineer",
        "Backend Lead",
    ],
    "locations": [
        "Noida",
        "Gurgaon",
        "Bangalore",
        "Hyderabad",
        "Remote",
    ],
    "daily_limit": 30,
}

INSTAHYRE = {
    "keywords": [""],
    "locations": [""],
    "daily_limit": 30,
}

WELLFOUND = {
    "keywords": [
        "backend-engineer",
        "software-engineer",
    ],
    "locations": [""],
    "daily_limit": 30,
}

CUTSHORT = {
    "keywords": [
        "backend-developer",
        "senior-software-engineer",
    ],
    "locations": [""],
    "daily_limit": 30,
}

DAILY_REFERRAL_TARGET = 5
DAILY_RECRUITER_TARGET = 2

EXPERIENCE_MIN_YEARS = 5

# ── Form auto-fill defaults ──────────────────────────────────────────
# These are used to auto-fill application forms (e.g. LinkedIn Easy Apply)
PREFERRED_EMAIL = "your_email@example.com"
PHONE_NUMBER = "0000000000"
TOTAL_EXPERIENCE_YEARS = 6
CURRENT_CTC_LAKHS = 0
EXPECTED_CTC_LAKHS = 0
PREFERRED_CITY = "Bangalore"

LINKEDIN_PROFILE_URL = "https://www.linkedin.com/in/your-profile/"
GITHUB_URL = "https://github.com/your-username"
GRADUATION_YEAR = "2020"
COLLEGE = ""
HEADLINE = "Senior Backend Engineer | X+ Years"

# ── Company lists ─────────────────────────────────────────────────────
BLACKLISTED_COMPANIES = [
    # Add companies you don't want to apply to
]

TARGET_COMPANIES = [
    "Uber", "Flipkart", "Swiggy", "Meesho", "Razorpay",
    "PhonePe", "Gojek", "CRED", "Amazon", "Atlassian",
    "Zepto", "Groww", "Slice", "Porter", "ShareChat",
    "Google", "Microsoft", "Meta", "Apple", "Netflix",
]

# ── Paths (auto-derived, usually no need to change) ──────────────────
RESUME_PATH = os.path.join(os.path.dirname(__file__), "resume.pdf")
APPLIED_JOBS_PATH = os.path.join(os.path.dirname(__file__), "applied_jobs.json")
PIPELINE_PATH = os.path.join(os.path.dirname(__file__), "pipeline.csv")
UNKNOWN_FIELDS_PATH = os.path.join(os.path.dirname(__file__), "unknown_fields.json")

CHROME_DRIVER_PATH = None   # Set if chromedriver is not on PATH
HEADLESS = False             # Set True to run browser without GUI

# Bot uses its own Chrome profile directory so it never conflicts with
# your regular Chrome.  On first run you log in manually once — after
# that the sessions are saved and reused automatically.
BOT_CHROME_PROFILE_DIR = os.path.join(os.path.dirname(__file__), ".chrome_profile")
