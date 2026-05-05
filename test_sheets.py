"""
test_sheets.py
==============
Standalone test for Google Sheets logging.
Run this directly — does NOT need Streamlit.

Usage:
    python test_sheets.py path/to/sheets_service_account.json YOUR_SHEET_ID

Example:
    python test_sheets.py credentials/sheets_service_account.json 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
"""

import sys
import json
from datetime import datetime
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("Usage: python test_sheets.py <service_account.json> <sheet_id>")
        print()
        print("Example:")
        print("  python test_sheets.py credentials/sheets_service_account.json 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms")
        sys.exit(1)

    sa_file = Path(sys.argv[1])
    sheet_id = sys.argv[2]

    # ── Step 1: Check service account file ────────────────────────────────────
    print(f"\n[1/4] Checking service account file: {sa_file}")
    if not sa_file.exists():
        print(f"  ❌ File not found: {sa_file}")
        sys.exit(1)
    try:
        creds_info = json.loads(sa_file.read_text())
        print(f"  ✅ File loaded OK")
        print(f"  ✅ Service account email: {creds_info.get('client_email', '???')}")
    except Exception as e:
        print(f"  ❌ Failed to parse JSON: {e}")
        sys.exit(1)

    # ── Step 2: Authenticate ───────────────────────────────────────────────────
    print(f"\n[2/4] Authenticating with Google...")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        print(f"  ✅ Authenticated OK")
    except ImportError as e:
        print(f"  ❌ Missing library: {e}")
        print(f"     Run: pip install gspread google-auth")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ Auth failed: {e}")
        sys.exit(1)

    # ── Step 3: Open the sheet ─────────────────────────────────────────────────
    print(f"\n[3/4] Opening Google Sheet: {sheet_id}")
    try:
        sheet = client.open_by_key(sheet_id).sheet1
        print(f"  ✅ Sheet opened: '{sheet.title}'")
        existing = sheet.row_values(1)
        if existing:
            print(f"  ✅ Headers found: {existing}")
        else:
            print(f"  ℹ️  Sheet is empty — headers will be created")
            headers = ["Date", "Time", "Title", "Platforms", "Privacy", "YouTube URLs", "TikTok Status"]
            sheet.append_row(headers)
            print(f"  ✅ Headers created")
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"  ❌ SpreadsheetNotFound (404)")
        print(f"     Check that:")
        print(f"     1. The sheet ID is correct (it's the long string in the Google Sheets URL)")
        print(f"     2. You shared the sheet with: {creds_info.get('client_email', 'the service account email')}")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ Failed to open sheet: {e}")
        sys.exit(1)

    # ── Step 4: Write a test row ───────────────────────────────────────────────
    print(f"\n[4/4] Writing test row...")
    try:
        now = datetime.now()
        sheet.append_row([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M"),
            "TEST — CLI test row",
            "YT account1, TikTok",
            "Private",
            "https://youtu.be/test123",
            "PUBLISH_COMPLETE",
        ])
        print(f"  ✅ Row written successfully!")
        print(f"\n✅ All tests passed. Check your Google Sheet for the new row.")
    except Exception as e:
        print(f"  ❌ Failed to write row: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
