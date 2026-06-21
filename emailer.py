"""
emailer.py
----------
Replaces GmailApp.sendEmail() from the Apps Script version.

Uses plain SMTP with a Gmail "App Password" (simplest, no OAuth consent
screen needed). See README for how to generate one.
"""

from __future__ import annotations
import smtplib
from email.mime.text import MIMEText
from typing import List

from scanner import JobMatch


def build_email_body(jobs: List[JobMatch], recipient_name: str = "there") -> str:
    lines = [f"Hi {recipient_name},", "", "New product roles were detected on the following career pages:", ""]
    for job in jobs:
        lines.append("──────────────────────")
        lines.append(f"🏢 Company:  {job.company}")
        lines.append(f"🔍 Matched:  \"{job.keyword}\"")
        lines.append(f"🔗 Link:     {job.url}")
        lines.append(f"🕐 Found at: {job.found_at}")
        lines.append("")
    lines.append("──────────────────────")
    lines.append("Visit each link above to view the full job listing.")
    lines.append("")
    lines.append("Good luck!")
    lines.append("— Your Job Alert Dashboard")
    return "\n".join(lines)


def send_alert_email(
    jobs: List[JobMatch],
    sender_email: str,
    sender_app_password: str,
    recipient_email: str,
    recipient_name: str = "there",
):
    if not jobs:
        return

    subject = f"🚀 Job Alert: {len(jobs)} new PM/BA opening(s) found!"
    body = build_email_body(jobs, recipient_name)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_app_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
