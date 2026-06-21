# PM/BA Job Alert Dashboard — Setup Guide

## What this is (read this first)

This is a **Streamlit dashboard**, built to work *alongside* your existing
Google Apps Script — not replace it.

**Why not replace it?** Streamlit apps only run code while a browser tab is
open or a button is clicked. There is no built-in scheduler that fires
"every hour, forever, even with no tab open." Your Apps Script trigger
already does that for free. So the setup is:

| Job | Who does it |
|---|---|
| Check career pages every hour, 24/7, automatically | **Google Apps Script** (unchanged, keep it running) |
| Browse job history, search/filter, run a check on demand | **This Streamlit dashboard** |

Both read and write to the **same Google Sheet**, so they stay in sync.

---

## Part 1 — One-time Google Cloud setup (≈10 minutes)

You need a **service account** so Streamlit can talk to your Google Sheet
without you logging in every time.

1. Go to **https://console.cloud.google.com/**
2. Create a new project (or use an existing one) — top-left dropdown → "New Project"
3. In the search bar, search **"Google Sheets API"** → click it → click **Enable**
4. Also search **"Google Drive API"** → click it → click **Enable**
5. Go to **APIs & Services → Credentials** (left sidebar)
6. Click **+ Create Credentials → Service account**
7. Give it any name (e.g. `job-alert-bot`) → Create and continue → Done
8. Click on the service account you just created → go to the **Keys** tab
9. Click **Add Key → Create new key → JSON** → it downloads a `.json` file
   - **Keep this file private** — it's like a password.
10. Open that JSON file in a text editor — you'll paste its full contents into
    the Streamlit sidebar later.
11. Copy the service account's **email address** (looks like
    `job-alert-bot@your-project.iam.gserviceaccount.com`) — it's also visible
    inside the JSON file as `client_email`.

## Part 2 — Share your Google Sheet with the service account

1. Open the same Google Sheet your Apps Script already writes to
   (the one with the `SeenJobs` tab).
2. Click **Share** (top right).
3. Paste in the service account email from step 11 above.
4. Set its role to **Editor**.
5. Click **Send / Share**.

## Part 3 — Get your Spreadsheet ID

Look at your sheet's URL:

```
https://docs.google.com/spreadsheets/d/1AbCxyz_THIS_LONG_PART_IS_YOUR_ID/edit
```

Copy the long string between `/d/` and `/edit`. That's your **Spreadsheet ID**.

## Part 4 — Gmail App Password (for email alerts)

Regular Gmail passwords don't work for sending mail via code. You need an
**App Password**:

1. Go to **https://myaccount.google.com/security**
2. Make sure **2-Step Verification** is turned on (required for app passwords).
3. Go to **https://myaccount.google.com/apppasswords**
4. Create a new app password (name it e.g. "Job Alert Dashboard")
5. Copy the 16-character password it gives you — you'll paste this into the
   dashboard's sidebar (not your real Gmail password).

---

## Part 5 — Running the dashboard

### Option A — Run locally on your own computer (recommended to start)

1. Make sure you have Python 3.9+ installed.
2. Download all the files from this conversation into one folder:
   - `app.py`
   - `scanner.py`
   - `sheets_client.py`
   - `emailer.py`
   - `requirements.txt`
3. Open a terminal in that folder and run:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the app:
   ```bash
   streamlit run app.py
   ```
5. It opens automatically in your browser at `http://localhost:8501`.

### Option B — Deploy for free on Streamlit Community Cloud

1. Create a free GitHub account if you don't have one.
2. Create a new GitHub repo, upload the same 5 files.
3. Go to **https://share.streamlit.io/** → sign in with GitHub.
4. Click **New app** → pick your repo → set main file to `app.py` → **Deploy**.
5. You'll get a public URL like `https://your-app-name.streamlit.app`.
   - ⚠️ Anyone with this link can open the dashboard's *interface*, but they
     still can't see your data unless they also have your service account
     JSON and app password (those live only in your browser session, not in
     the code). For real protection, consider Streamlit's built-in
     password-protection via `st.secrets` + a simple login check, or keep
     the URL private.

---

## Part 6 — Using the dashboard, step by step

1. **Open the app** (locally or via your deployed URL).
2. In the **left sidebar**, expand **"Google Sheets connection"**:
   - Paste the full contents of your service account JSON file.
   - Paste your Spreadsheet ID.
3. Expand **"Email alert settings"**:
   - Enter your Gmail address (the one that will *send* alerts).
   - Paste the 16-character App Password from Part 4.
   - Enter the email address that should *receive* alerts (can be the same).
4. Go to the **📋 Dashboard tab** — you should now see your existing job
   history pulled live from the Sheet. Use the search box to filter by
   company or keyword.
5. Go to the **🔍 Check Now tab**:
   - Leave the company list empty to scan **all 48 companies**, or pick
     specific ones from the dropdown to scan just those.
   - Tick **"Email me if new jobs are found"** if you want an alert sent
     immediately when this manual scan finds something.
   - Click **▶️ Run Check Now**.
   - Watch the progress bar — it checks each company's career page one by
     one and shows a live log underneath.
   - If new matches are found, they're shown in a table, saved to your
     Google Sheet, and (if ticked) emailed to you.
6. Use **🗑️ Reset history** on the Dashboard tab if you ever want to wipe
   the "seen jobs" log and start fresh (this affects the shared Sheet, so it
   also resets what Apps Script considers "already seen").

---

## Keeping the Apps Script running

Nothing about your existing Apps Script needs to change. It will keep:
- Running every hour automatically
- Writing new matches to the same `SeenJobs` sheet
- Emailing you via `GmailApp.sendEmail`

The dashboard simply reads/writes the same sheet, so anything Apps Script
finds will show up here too, and anything you find here (via Check Now)
won't be re-flagged by Apps Script later.

---

## Known limitations (carried over from the original script, plus new ones)

- **JavaScript-rendered career pages**: Some companies (especially ones using
  Greenhouse, Lever, or custom React career pages) load job listings via
  JavaScript *after* the page loads. Both the original Apps Script
  (`UrlFetchApp`) and this Python version (`requests`) only see the raw
  HTML before JavaScript runs, so they may miss jobs on those sites. If a
  company consistently shows 0 matches even when you know they're hiring,
  this is the likely reason — a future upgrade could add headless-browser
  rendering for just those sites.
- **Bot blocking**: A few sites block requests that don't look like a real
  browser. The scanner sends a basic User-Agent header to reduce this, but
  some sites may still return 403 errors. These show up clearly in the scan
  log so you know which companies to check manually instead.
- **Keyword matching is a simple substring check**: just like the original,
  it doesn't understand context, so a page that mentions "product manager"
  in an unrelated sentence (e.g. a blog post linked from the careers page)
  could register as a false positive.
