"""
scanner.py
----------
Python port of the Apps Script keyword-matching logic.

This replaces:
- findKeywordMatches()  -> same keyword substring check, case-insensitive
- the UrlFetchApp.fetch() loop inside checkJobAlerts()

Design notes:
- Streamlit has no background scheduler, so this module is only ever
  triggered by a human clicking "Check Now" in the UI, OR by an external
  cron/script calling run_scan() directly (see README "Option B").
- Companies are fetched with a short timeout and individual try/except,
  exactly like the original script, so one slow/broken career page
  doesn't kill the whole batch.
"""

from __future__ import annotations
import datetime
from dataclasses import dataclass
from typing import List, Set

import requests

FETCH_TIMEOUT_SECONDS = 10

KEYWORDS = [
    "product manager",
    "business analyst",
    "senior pm",
    "associate product manager",
    "product owner",
    "growth product",
]

COMPANIES = [
    # FINTECH
    {"name": "Razorpay", "url": "https://razorpay.com/jobs/"},
    {"name": "PhonePe", "url": "https://phonepe.com/en/careers.html"},
    {"name": "CRED", "url": "https://careers.cred.club/"},
    {"name": "EnKash", "url": "https://enkash.com/careers/"},
    {"name": "BharatPe", "url": "https://bharatpe.com/careers"},
    {"name": "Groww", "url": "https://groww.in/careers"},
    {"name": "Zerodha", "url": "https://zerodha.com/careers"},
    {"name": "Juspay", "url": "https://juspay.in/careers"},
    {"name": "Cashfree", "url": "https://www.cashfree.com/careers/"},
    {"name": "Paytm", "url": "https://paytm.com/about-us/careers"},
    # FOOD & QUICK COMMERCE
    {"name": "Zomato", "url": "https://www.zomato.com/careers"},
    {"name": "Swiggy", "url": "https://careers.swiggy.com/"},
    {"name": "Zepto", "url": "https://www.zepto.team/careers"},
    {"name": "BigBasket", "url": "https://careers.bigbasket.com/"},
    # B2B SAAS
    {"name": "Freshworks", "url": "https://careers.freshworks.com/jobs"},
    {"name": "Chargebee", "url": "https://www.chargebee.com/careers/"},
    {"name": "Postman", "url": "https://www.postman.com/company/careers/"},
    {"name": "Darwinbox", "url": "https://darwinbox.com/careers"},
    {"name": "Clevertap", "url": "https://clevertap.com/careers/"},
    {"name": "MoEngage", "url": "https://www.moengage.com/careers/"},
    {"name": "WebEngage", "url": "https://webengage.com/careers/"},
    {"name": "Browserstack", "url": "https://www.browserstack.com/careers"},
    {"name": "Exotel", "url": "https://exotel.com/careers/"},
    {"name": "Zoho", "url": "https://careers.zohocorp.com/"},
    {"name": "Leadsquared", "url": "https://www.leadsquared.com/careers/"},
    # E-COMMERCE
    {"name": "Meesho", "url": "https://meesho.io/jobs"},
    {"name": "Nykaa", "url": "https://www.nykaa.com/careers"},
    {"name": "Myntra", "url": "https://www.myntra.com/careers"},
    {"name": "Urban Company", "url": "https://urbancompany.com/careers"},
    {"name": "Lenskart", "url": "https://lenskart.com/careers"},
    {"name": "Cars24", "url": "https://cars24.com/careers/"},
    # MOBILITY
    {"name": "Rapido", "url": "https://rapido.bike/careers"},
    {"name": "Ola", "url": "https://ola.careers/"},
    # TRAVEL
    {"name": "MakeMyTrip", "url": "https://careers.makemytrip.com/"},
    {"name": "ixigo", "url": "https://www.ixigo.com/careers"},
    {"name": "Cleartrip", "url": "https://careers.cleartrip.com/"},
    # HEALTHTECH
    {"name": "Practo", "url": "https://practo.com/careers"},
    {"name": "Innovaccer", "url": "https://innovaccer.com/careers/"},
    {"name": "Cult.fit", "url": "https://cult.fit/careers"},
    {"name": "1mg", "url": "https://www.1mg.com/careers"},
    # EDTECH
    {"name": "PhysicsWallah", "url": "https://careers.pw.live/"},
    {"name": "Unacademy", "url": "https://unacademy.com/careers"},
    {"name": "Scaler", "url": "https://scaler.com/careers/"},
    {"name": "Classplus", "url": "https://classplus.co/careers"},
    # CONSUMER & SOCIAL
    {"name": "ShareChat", "url": "https://sharechat.com/careers"},
    {"name": "Truecaller", "url": "https://truecaller.com/careers"},
    {"name": "InMobi", "url": "https://inmobi.com/company/careers/"},
    {"name": "Khatabook", "url": "https://khatabook.com/careers/"},
]


@dataclass
class JobMatch:
    company: str
    keyword: str
    url: str
    found_at: str
    job_key: str


def _now_ist_string() -> str:
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).strftime("%d/%m/%Y, %H:%M:%S")


def _find_keyword_matches(html_lower: str, company_name: str, url: str) -> List[JobMatch]:
    found = []
    for keyword in KEYWORDS:
        if keyword.lower() in html_lower:
            found.append(
                JobMatch(
                    company=company_name,
                    keyword=keyword,
                    url=url,
                    found_at=_now_ist_string(),
                    job_key=f"{company_name}|{keyword}",
                )
            )
    return found


def scan_companies(companies: List[dict], seen_jobs: Set[str], progress_callback=None):
    """
    Scans the given list of company dicts ({"name", "url"}).
    Returns (new_jobs: list[JobMatch], log_lines: list[str]).

    progress_callback(i, total, company_name) is called before each fetch,
    so the Streamlit UI can show a live progress bar.
    """
    new_jobs: List[JobMatch] = []
    log_lines: List[str] = []
    total = len(companies)

    for i, company in enumerate(companies):
        if progress_callback:
            progress_callback(i, total, company["name"])

        try:
            resp = requests.get(
                company["url"],
                timeout=FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": "Mozilla/5.0 (JobAlertBot/1.0)"},
                allow_redirects=True,
            )
            if resp.status_code != 200:
                log_lines.append(f"{company['name']}: HTTP {resp.status_code}, skipping")
                continue

            html_lower = resp.text.lower()
            matches = _find_keyword_matches(html_lower, company["name"], company["url"])

            new_count = 0
            for m in matches:
                if m.job_key not in seen_jobs:
                    new_jobs.append(m)
                    seen_jobs.add(m.job_key)  # avoid dup within same run
                    new_count += 1

            log_lines.append(f"{company['name']}: OK ({len(matches)} matches, {new_count} new)")

        except requests.exceptions.Timeout:
            log_lines.append(f"{company['name']}: Timeout, skipping")
        except Exception as e:
            log_lines.append(f"{company['name']}: Error — {e}")

    return new_jobs, log_lines
