"""
sheets_logger.py
Persistent post history stored in a Google Sheet.
Uses a service account for auth — no user OAuth needed.

Sheet columns: Date | Time | Title | Platforms | Privacy | YouTube URLs | TikTok Status
"""

import json
from datetime import datetime

import streamlit as st

SHEET_HEADERS = ["Date", "Time", "Title", "Platforms", "Privacy", "YouTube URLs", "TikTok Status"]


def _get_client():
    """Return an authorised gspread client. Cached per app session."""
    import gspread

    raw = st.secrets["sheets_service_account"]
    # Streamlit TOML may pre-expand \n inside the JSON string into real newlines,
    # making json.loads() reject them as control characters. strict=False allows it.
    if isinstance(raw, str):
        creds_info = json.JSONDecoder(strict=False).decode(raw)
    else:
        creds_info = dict(raw)  # already a TOML table / dict
    return gspread.service_account_from_dict(creds_info)


def _get_sheet():
    """Open the configured sheet and ensure the header row exists."""
    client = _get_client()
    sheet_id = st.secrets["sheets_id"]
    sheet = client.open_by_key(sheet_id).sheet1

    # Create header row if the sheet is empty
    existing = sheet.row_values(1)
    if not existing:
        sheet.append_row(SHEET_HEADERS)

    return sheet


def load_history() -> list[dict]:
    """
    Load all post history rows from Google Sheets.
    Returns a list of dicts matching the app's history format:
        {"title": str, "time": str, "platforms": str, "date": str}
    Returns an empty list (silently) if sheets is not configured or fails.
    """
    if "sheets_service_account" not in st.secrets or "sheets_id" not in st.secrets:
        return []
    try:
        sheet = _get_sheet()
        records = sheet.get_all_records()
        history = []
        for r in records:
            history.append({
                "title": r.get("Title", ""),
                "time": r.get("Time", ""),
                "platforms": r.get("Platforms", ""),
                "date": r.get("Date", ""),
                "privacy": r.get("Privacy", ""),
                "yt_urls": r.get("YouTube URLs", ""),
                "tt_status": r.get("TikTok Status", ""),
            })
        return history
    except Exception:
        return []


def log_post(title: str, platforms: str, privacy: str, results: list) -> bool:
    """
    Append one post record to Google Sheets.
    Returns True on success, raises Exception on failure so caller can show the error.
    """
    if "sheets_service_account" not in st.secrets or "sheets_id" not in st.secrets:
        return False
    # Let exceptions bubble up so the caller can display them
    sheet = _get_sheet()
    now = datetime.now()

    yt_urls = ", ".join(r.get("url", "") for r in results if "url" in r)
    tt_status = next(
        (r.get("status", "") for r in results if r.get("platform") == "tiktok"),
        "",
    )

    sheet.append_row([
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        title,
        platforms,
        privacy.title(),
        yt_urls,
        tt_status,
    ])
    return True
