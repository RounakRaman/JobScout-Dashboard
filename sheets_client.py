"""
sheets_client.py
-----------------
Thin wrapper around the Google Sheets API.

This replaces what SpreadsheetApp did inside Apps Script:
- getOrCreateSheet()  -> ensures a "SeenJobs" tab exists with headers
- getSeenJobs()       -> returns the set of already-seen job keys
- markJobSeen()       -> appends a new row when a new job is found

Auth: uses a Google Cloud "service account" JSON key file.
You will generate this once during setup (see README) and share your
Google Sheet with the service account's email address as an Editor.
"""

from __future__ import annotations
import datetime
from typing import Set, List, Dict

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SEEN_SHEET_NAME = "SeenJobs"
HEADER_ROW = ["Job Key", "Date Seen"]


class SheetsClient:
    def __init__(self, service_account_info: dict, spreadsheet_id: str):
        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        self._gc = gspread.authorize(creds)
        self._sh = self._gc.open_by_key(spreadsheet_id)
        self._ws_cache = None  # cached worksheet handle, fetched once

    # ---- sheet bootstrap -------------------------------------------------

    def get_or_create_seen_sheet(self):
        if self._ws_cache is not None:
            return self._ws_cache
        try:
            ws = self._sh.worksheet(SEEN_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = self._sh.add_worksheet(title=SEEN_SHEET_NAME, rows=1000, cols=2)
            ws.append_row(HEADER_ROW)
        self._ws_cache = ws
        return ws

    # ---- reads -------------------------------------------------------------

    def get_seen_jobs(self) -> Set[str]:
        ws = self.get_or_create_seen_sheet()
        rows = ws.get_all_values()
        seen = set()
        for row in rows[1:]:  # skip header
            if row and row[0]:
                seen.add(row[0])
        return seen

    def get_all_rows(self) -> List[Dict[str, str]]:
        """Returns every logged row as dicts, most recent first, for display in the UI."""
        ws = self.get_or_create_seen_sheet()
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        records = [{"Job Key": r[0], "Date Seen": r[1] if len(r) > 1 else ""} for r in rows[1:]]
        return list(reversed(records))

    # ---- writes ----------------------------------------------------------

    def mark_job_seen(self, job_key: str):
        ws = self.get_or_create_seen_sheet()
        now_ist = _now_ist_string()
        ws.append_row([job_key, now_ist])

    def reset_seen_jobs(self):
        ws = self.get_or_create_seen_sheet()
        ws.clear()
        ws.append_row(HEADER_ROW)


def _now_ist_string() -> str:
    # Matches the Apps Script "en-IN" / Asia/Kolkata formatting closely enough
    # for human reading purposes inside the sheet.
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).strftime("%d/%m/%Y, %H:%M:%S")
