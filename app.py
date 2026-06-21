"""
app.py
------
PM/BA Job Alert Dashboard — Streamlit version.

This is a CONTROL PANEL for the job-alert system, not a replacement for the
always-on background checker. The Google Apps Script trigger should keep
running hourly in the background (it's free and doesn't need a server).
This dashboard:
  - Reads the live "SeenJobs" history from your Google Sheet
  - Lets you manually trigger a full or partial scan ("Check Now")
  - Sends you an email if the manual scan finds something new
  - Lets you search/filter what's already been found
  - Lets you reset the seen-jobs history

See README.md for full setup steps.
"""

import json
import time
import datetime

import streamlit as st
import pandas as pd

from sheets_client import SheetsClient
from scanner import COMPANIES, scan_companies
from emailer import send_alert_email

st.set_page_config(
    page_title="Job Alert Dashboard",
    page_icon="🚀",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar — connection & email settings
# ---------------------------------------------------------------------------

st.sidebar.header("⚙️ Settings")

with st.sidebar.expander("Google Sheets connection", expanded=False):
    st.caption(
        "Paste your service-account JSON and the target Spreadsheet ID. "
        "These stay in this browser session only — nothing is saved to disk "
        "unless you're running locally and choose to use st.secrets."
    )
    sa_json_text = st.text_area(
        "Service account JSON",
        value=st.session_state.get("sa_json_text", ""),
        height=120,
        help="The full contents of the .json key file downloaded from Google Cloud.",
    )
    spreadsheet_id = st.text_input(
        "Spreadsheet ID",
        value=st.session_state.get("spreadsheet_id", ""),
        help="The long ID in your sheet's URL: docs.google.com/spreadsheets/d/THIS_PART/edit",
    )
    if sa_json_text:
        st.session_state["sa_json_text"] = sa_json_text
    if spreadsheet_id:
        st.session_state["spreadsheet_id"] = spreadsheet_id

with st.sidebar.expander("Email alert settings", expanded=False):
    sender_email = st.text_input("Sender Gmail address", value=st.session_state.get("sender_email", ""))
    sender_app_password = st.text_input(
        "Gmail App Password", type="password", value=st.session_state.get("sender_app_password", "")
    )
    recipient_email = st.text_input("Send alerts to", value=st.session_state.get("recipient_email", sender_email))
    recipient_name = st.text_input("Greeting name", value=st.session_state.get("recipient_name", "there"))
    for key, val in [
        ("sender_email", sender_email),
        ("sender_app_password", sender_app_password),
        ("recipient_email", recipient_email),
        ("recipient_name", recipient_name),
    ]:
        st.session_state[key] = val

st.sidebar.divider()
st.sidebar.caption(
    "💡 The hourly background checker still runs in **Google Apps Script** — "
    "this dashboard reads the same Google Sheet and lets you trigger checks "
    "manually. See the README tab for why."
)

# ---------------------------------------------------------------------------
# Connect to Sheet (cached per session)
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def _build_client(sa_text: str, sheet_id: str):
    """
    Cached so the gspread connection (and the underlying API calls it makes)
    is only created ONCE per unique (sa_text, sheet_id) pair, instead of on
    every Streamlit rerun. This is what was causing the 429 quota error —
    Streamlit reruns the whole script on every keystroke/click, and without
    caching that meant a fresh API connection every single time.
    """
    sa_info = json.loads(sa_text)
    return SheetsClient(sa_info, sheet_id)


def get_client():
    sa_text = st.session_state.get("sa_json_text", "")
    sheet_id = st.session_state.get("spreadsheet_id", "")
    if not sa_text or not sheet_id:
        return None, "Add your service account JSON and Spreadsheet ID in the sidebar to connect."
    try:
        json.loads(sa_text)
    except json.JSONDecodeError:
        return None, "That doesn't look like valid JSON. Paste the full key file contents."
    try:
        client = _build_client(sa_text, sheet_id)
        return client, None
    except Exception as e:
        err_text = str(e)
        if "429" in err_text or "Quota exceeded" in err_text:
            return None, (
                "Google's API rate limit was hit (this resets automatically every minute). "
                "Wait about 60 seconds, then click Refresh or reload the page."
            )
        return None, f"Couldn't connect to the sheet: {e}"


client, conn_error = get_client()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🚀 PM / BA Job Alert Dashboard")
st.caption("Tracking product & business analyst openings across 48 companies' career pages.")

if conn_error:
    st.warning(conn_error)
    st.info(
        "Open the **README** tab below for the full step-by-step setup — "
        "you'll need a Google service account and to share your sheet with it."
    )

tab_dashboard, tab_checknow, tab_readme = st.tabs(["📋 Dashboard", "🔍 Check Now", "📖 Setup Guide"])

# ---------------------------------------------------------------------------
# TAB 1 — Dashboard (read history)
# ---------------------------------------------------------------------------

with tab_dashboard:
    if not client:
        st.info("Connect your sheet in the sidebar to see job history here.")
    else:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search = st.text_input("🔎 Filter by company or keyword", "")
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with col3:
            if st.button("🗑️ Reset history", use_container_width=True):
                st.session_state["confirm_reset"] = True

        if st.session_state.get("confirm_reset"):
            st.error("This clears all 'seen jobs' history — future scans will treat everything as new again.")
            c1, c2 = st.columns(2)
            if c1.button("Yes, reset it"):
                client.reset_seen_jobs()
                st.session_state["confirm_reset"] = False
                st.success("History cleared.")
                st.rerun()
            if c2.button("Cancel"):
                st.session_state["confirm_reset"] = False
                st.rerun()

        records = client.get_all_rows()
        if not records:
            st.info("No jobs logged yet. Run a check from the **Check Now** tab, or wait for the Apps Script trigger.")
        else:
            df = pd.DataFrame(records)
            df["Company"] = df["Job Key"].str.split("|").str[0]
            df["Matched Keyword"] = df["Job Key"].str.split("|").str[1]
            df = df[["Date Seen", "Company", "Matched Keyword"]]

            if search:
                mask = df["Company"].str.contains(search, case=False, na=False) | df["Matched Keyword"].str.contains(
                    search, case=False, na=False
                )
                df = df[mask]

            m1, m2 = st.columns(2)
            m1.metric("Total matches logged", len(records))
            m2.metric("Showing", len(df))

            st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# TAB 2 — Check Now (manual scan)
# ---------------------------------------------------------------------------

with tab_checknow:
    st.subheader("Run a manual scan")
    st.caption(
        "This fetches each company's career page right now and checks for your keywords. "
        "Scanning all 47 companies takes roughly 1–3 minutes depending on site speed."
    )

    company_names = [c["name"] for c in COMPANIES]
    selected = st.multiselect(
        "Companies to check (leave empty to check ALL)",
        options=company_names,
        default=[],
    )
    companies_to_scan = (
        [c for c in COMPANIES if c["name"] in selected] if selected else COMPANIES
    )

    send_email_on_find = st.checkbox("📧 Email me if new jobs are found", value=True)

    run = st.button("▶️ Run Check Now", type="primary", disabled=(client is None))
    if client is None:
        st.caption("Connect your Google Sheet in the sidebar first.")

    if run and client:
        seen_jobs = client.get_seen_jobs()

        progress_bar = st.progress(0, text="Starting scan...")
        log_box = st.empty()
        logs = []

        def on_progress(i, total, name):
            progress_bar.progress((i) / total, text=f"Checking {name} ({i + 1}/{total})...")

        new_jobs, log_lines = scan_companies(companies_to_scan, seen_jobs, progress_callback=on_progress)
        progress_bar.progress(1.0, text="Scan complete.")

        logs.extend(log_lines)
        log_box.code("\n".join(logs), language=None)

        if new_jobs:
            st.success(f"🎉 Found {len(new_jobs)} new match(es)!")
            for job in new_jobs:
                client.mark_job_seen(job.job_key)

            new_df = pd.DataFrame(
                [{"Company": j.company, "Matched Keyword": j.keyword, "Link": j.url, "Found At": j.found_at} for j in new_jobs]
            )
            st.dataframe(new_df, use_container_width=True, hide_index=True)

            if send_email_on_find:
                se = st.session_state.get("sender_email")
                sp = st.session_state.get("sender_app_password")
                re_ = st.session_state.get("recipient_email")
                rn = st.session_state.get("recipient_name", "there")
                if se and sp and re_:
                    try:
                        send_alert_email(new_jobs, se, sp, re_, rn)
                        st.success(f"📧 Alert email sent to {re_}.")
                    except Exception as e:
                        st.error(f"Found jobs, but the email failed to send: {e}")
                else:
                    st.warning("Add your email settings in the sidebar to enable alert emails.")
        else:
            st.info("No new matches this run — everything found was already logged before.")

# ---------------------------------------------------------------------------
# TAB 3 — README / setup guide (also see the full README.md file)
# ---------------------------------------------------------------------------

with tab_readme:
    st.markdown(
        """
### Quick orientation

This dashboard is a **companion** to your existing Google Apps Script,
not a replacement for it. Streamlit apps don't run in the background on
their own — they only execute code while a page is open or a button is
clicked. So:

- **Apps Script** keeps doing the hourly automatic checking + emailing, exactly as before.
- **This dashboard** gives you a nice UI to browse what's been found, search/filter,
  and run an on-demand check any time you want — without opening the Apps Script editor.

Full setup steps are in the **README.md** file delivered alongside this app.
        """
    )
