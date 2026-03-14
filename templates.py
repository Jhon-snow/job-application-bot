REFERRAL_TEMPLATE = """Hi {name},

I came across your profile while exploring backend engineering roles at {company}.

I have around {years} years of experience building scalable backend systems \
(Python, distributed systems, databases, microservices).

I'm currently exploring SDE3 backend opportunities and noticed an open role at {company}.
Would you be open to referring me for this position?

Happy to share my resume.

Thanks!"""

RECRUITER_TEMPLATE = """Hi {name},

I'm a backend engineer with {years} years of experience working on scalable distributed systems.

My recent work includes:
- High scale APIs
- Distributed processing systems
- Database scaling (replicas, sharding)

I'm exploring Senior Backend / SDE3 opportunities.

Would love to connect if there are relevant openings.

Thanks!"""

COLD_EMAIL_TEMPLATE = """Subject: Senior Backend Engineer - Open to Opportunities

Hi {name},

I'm a backend engineer with {years} years of experience in building \
high-throughput distributed systems.

Key highlights:
- Designed APIs handling {daily_requests}+ daily requests
- Built distributed processing pipelines using Python and message queues
- Optimized database performance (indexing, query refactoring, read-replicas)

I noticed {company} is hiring for backend roles and I'd love to explore \
SDE3 / Senior Backend opportunities.

Attached is my resume for your reference.

Best,
{your_name}"""


def generate_referral_message(
    name: str, company: str, years: int = 6
) -> str:
    return REFERRAL_TEMPLATE.format(name=name, company=company, years=years)


def generate_recruiter_message(name: str, years: int = 6) -> str:
    return RECRUITER_TEMPLATE.format(name=name, years=years)


def generate_cold_email(
    name: str,
    company: str,
    your_name: str = "Your Name",
    years: int = 6,
    daily_requests: str = "2M",
) -> str:
    return COLD_EMAIL_TEMPLATE.format(
        name=name,
        company=company,
        your_name=your_name,
        years=years,
        daily_requests=daily_requests,
    )


def print_referral_messages(companies: list[str], years: int = 6):
    print(f"\n{'='*60}")
    print("  REFERRAL MESSAGE TEMPLATES")
    print(f"{'='*60}")
    for company in companies:
        print(f"\n--- {company} ---")
        print(generate_referral_message("<Name>", company, years))
    print(f"\n{'='*60}\n")


def print_recruiter_message(years: int = 6):
    print(f"\n{'='*60}")
    print("  RECRUITER OUTREACH TEMPLATE")
    print(f"{'='*60}")
    print(generate_recruiter_message("<Recruiter Name>", years))
    print(f"\n{'='*60}\n")
