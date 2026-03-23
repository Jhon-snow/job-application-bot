import re
from typing import Optional

CITY_ALIASES = {
    "bangalore": {"bengaluru", "bangalore"},
    "bengaluru": {"bengaluru", "bangalore"},
    "gurgaon": {"gurgaon", "gurugram"},
    "gurugram": {"gurgaon", "gurugram"},
    "mumbai": {"mumbai", "bombay"},
    "bombay": {"mumbai", "bombay"},
    "chennai": {"chennai", "madras"},
    "noida": {"noida", "greater noida"},
    "hyderabad": {"hyderabad", "secunderabad"},
    "pune": {"pune", "pimpri"},
}


BACKEND_KEYWORDS = {
    "backend", "back-end", "back end",
    "python", "java", "golang", "go ", "node",
    "distributed", "microservices", "api",
    "database", "sql", "nosql",
    "scalable", "high-throughput",
    "software engineer", "software developer", "software development",
    "sde", "swe", "sse",
    "ruby", "django", "flask", "spring",
    "mern", "mean",
}

SENIOR_KEYWORDS = {
    "senior", "sr.", "sr ", "sr-",
    "sde-2", "sde2", "sde 2", "sde-ii", "sde ii",
    "sde-3", "sde3", "sde 3", "sde-iii", "sde iii",
    "sde-4", "sde4", "sde 4", "sde-iv", "sde iv",
    "engineer ii", "engineer iii", "engineer iv",
    "engineer - ii", "engineer - iii", "engineer - iv",
    "staff", "lead", "principal", "l5", "l6", "l7",
    "engineering manager", "manager",
    "vp,", "vp ", "vice president",
    "director", "architect", "founding engineer",
    "member technical staff", "member of technical staff", "mts",
    "5+ years", "5-10 years", "4+ years",
}

EXCLUDE_KEYWORDS = {
    "intern", "internship", "fresher", "junior",
    "sde-1", "sde1", "sde 1", "sde-i ",
    "frontend only", "front-end only",
    "ios developer", "ios engineer", "ios application",
    "android developer", "android engineer",
    "mobile developer",
    "data analyst", "business analyst",
    "qa automation", "qa engineer", "quality assurance",
    "dft", "hvdc", "hardware",
    "unpaid",
    "php developer", "php programmer", "php engineer",
    "wordpress", "drupal", "laravel",
}

MAYBE_BACKEND_TITLES = {
    "software engineer", "software developer",
    "software development engineer", "full stack",
    "fullstack", "full-stack",
    "programmer",
}


def is_backend_role(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in BACKEND_KEYWORDS)


def is_maybe_backend(title: str) -> bool:
    """Titles that COULD be backend even without explicit backend keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in MAYBE_BACKEND_TITLES)


def is_excluded_role(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in EXCLUDE_KEYWORDS)


def is_senior_level(title: str) -> bool:
    title_lower = title.lower()
    if is_excluded_role(title):
        return False
    return any(kw in title_lower for kw in SENIOR_KEYWORDS)


def is_location_match(
    location: str,
    allowed_locations: list[str],
    search_location: str = "",
    wfo_ok_cities: set[str] | None = None,
    allow_unknown_job_location: bool = False,
) -> bool:
    """
    allow_unknown_job_location: for portals that don't pass a real search location
    and often omit location on cards (e.g. Cutshort) — accept empty job location.
    """
    if not (location or "").strip():
        if allow_unknown_job_location:
            return True
        return bool(search_location)

    location_lower = location.lower()
    stripped = (
        location_lower
        .replace("hybrid", "")
        .replace("work from office", "")
        .replace("in office", "")
        .replace("onsite or remote", "")
        .replace("onsite", "")
        .replace("work from home", "")
        .replace("on-site", "")
        .replace("on site", "")
        .replace("\u2013", "")  # em-dash used by Wellfound
        .replace("–", "")
        .replace("—", "")
        .strip(" -,()")
    )

    is_hybrid = "hybrid" in location_lower
    is_wfo = (
        "work from office" in location_lower
        or "in office" in location_lower
        or ("onsite" in location_lower and "remote" not in location_lower)
    )
    is_remote = (
        "remote" in location_lower
        or "work from home" in location_lower
        or "wfh" in location_lower
    )

    if is_remote:
        return True

    city_match = _any_city_match(stripped, allowed_locations) if stripped else False
    search_city = search_location.lower() if search_location else ""

    if is_hybrid:
        return city_match or bool(search_city)

    if is_wfo:
        if wfo_ok_cities:
            expanded = set()
            for c in wfo_ok_cities:
                expanded.update(CITY_ALIASES.get(c, {c}))
            if city_match:
                return any(c in stripped for c in expanded)
            if search_city:
                return any(c in search_city for c in expanded)
        return False

    return city_match


def _any_city_match(location_text: str, allowed_locations: list[str]) -> bool:
    """Check if location_text contains any allowed city, using aliases."""
    for loc in allowed_locations:
        loc_lower = loc.lower()
        names = CITY_ALIASES.get(loc_lower, {loc_lower})
        if any(name in location_text for name in names):
            return True
    return False


def is_company_blacklisted(company: str, blacklist: list[str]) -> bool:
    company_lower = company.lower()
    return any(bl.lower() in company_lower for bl in blacklist)


def matches_experience(description: str, min_years: int) -> bool:
    """Check if the job description mentions experience within acceptable range."""
    patterns = [
        r"(\d+)\+?\s*(?:years|yrs)",
        r"(\d+)\s*-\s*(\d+)\s*(?:years|yrs)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            groups = match.groups()
            low = int(groups[0])
            if low > min_years + 5:
                return False
    return True


def should_apply(
    title: str,
    company: str,
    location: str,
    description: str,
    allowed_locations: list[str],
    blacklisted_companies: list[str],
    min_experience: int,
    search_location: str = "",
    wfo_ok_cities: set[str] | None = None,
    relax_seniority: bool = False,
    allow_unknown_job_location: bool = False,
) -> tuple[bool, Optional[str]]:
    """
    Returns (should_apply, skip_reason).
    relax_seniority=True trusts the portal's own seniority filter (e.g.
    LinkedIn f_E=4) and only rejects explicit junior/intern titles.
    allow_unknown_job_location=True for portals with missing location text on cards.
    """
    if is_company_blacklisted(company, blacklisted_companies):
        return False, f"Blacklisted company: {company}"

    if is_excluded_role(title):
        return False, f"Excluded role: {title}"

    if not relax_seniority and not is_senior_level(title):
        return False, f"Not senior level: {title}"

    title_is_backend = is_backend_role(title)
    desc_is_backend = is_backend_role(description[:500]) if description else False
    title_maybe_backend = is_maybe_backend(title)

    if not title_is_backend and not desc_is_backend and not title_maybe_backend:
        return False, f"Not a backend role: {title}"

    if not is_location_match(
        location,
        allowed_locations,
        search_location,
        wfo_ok_cities,
        allow_unknown_job_location=allow_unknown_job_location,
    ):
        return False, f"Location mismatch: {location}"

    if description and not matches_experience(description, min_experience):
        return False, f"Experience mismatch for: {title}"

    return True, None
