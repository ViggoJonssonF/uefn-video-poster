"""
youtube_uploader.py
Handles OAuth authentication and video uploads for multiple YouTube accounts.
Each account uses its own client_secrets and token file stored in ./credentials/.
"""

import os
import time
import json
import pickle
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_DIR = Path(__file__).parent / "credentials"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Resumable upload chunk size: 10 MB
CHUNK_SIZE = 10 * 1024 * 1024

# Category IDs - 20 = Gaming
GAMING_CATEGORY_ID = "20"


def get_authenticated_service(account_name: str):
    """
    Returns an authenticated YouTube API service for the given account.
    On first run, opens a browser for OAuth consent and saves the token.
    On subsequent runs, loads and refreshes the saved token.

    Args:
        account_name: A short label for the account (e.g. "account1").
                      Must match the client_secrets file: credentials/youtube_secrets_{account_name}.json
    """
    token_path = CREDENTIALS_DIR / f"youtube_token_{account_name}.pkl"
    secrets_path = CREDENTIALS_DIR / f"youtube_secrets_{account_name}.json"

    if not secrets_path.exists():
        raise FileNotFoundError(
            f"Client secrets file not found: {secrets_path}\n"
            f"Please follow the SETUP_GUIDE.md to download your OAuth credentials "
            f"and save them as: {secrets_path}"
        )

    credentials = None

    # Load saved token if it exists
    if token_path.exists():
        with open(token_path, "rb") as f:
            credentials = pickle.load(f)

    # Refresh or re-authenticate if needed
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print(f"  [{account_name}] Refreshing expired token...")
            credentials.refresh(Request())
        else:
            print(f"  [{account_name}] Opening browser for OAuth login...")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            credentials = flow.run_local_server(port=0, prompt="consent")

        # Save the token for next time
        with open(token_path, "wb") as f:
            pickle.dump(credentials, f)
        print(f"  [{account_name}] Token saved to {token_path}")

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)


def upload_video(
    account_name: str,
    video_path: str,
    title: str,
    description: str,
    tags: list[str] = None,
    privacy_status: str = "public",
    category_id: str = GAMING_CATEGORY_ID,
) -> dict:
    """
    Uploads a video to YouTube for the specified account.

    Args:
        account_name:   Short label matching your credentials file (e.g. "account1").
        video_path:     Absolute or relative path to the video file.
        title:          Video title (max 100 chars).
        description:    Video description.
        tags:           List of tags (optional).
        privacy_status: "public", "unlisted", or "private".
        category_id:    YouTube category ID. Default 20 = Gaming.

    Returns:
        dict with keys: account, video_id, url, title
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    print(f"\n[YouTube] Uploading to {account_name}...")
    print(f"  File: {video_path.name} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

    youtube = get_authenticated_service(account_name)

    body = {
        "snippet": {
            "title": title[:100],  # YouTube max title length
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/*",
        resumable=True,
        chunksize=CHUNK_SIZE,
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    retry_count = 0
    max_retries = 5
    retry_exceptions = (HttpError,)

    while response is None:
        try:
            print(f"  [{account_name}] Uploading...", end="", flush=True)
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"\r  [{account_name}] Upload progress: {progress}%", end="", flush=True)
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504] and retry_count < max_retries:
                retry_count += 1
                wait = 2 ** retry_count
                print(f"\n  [{account_name}] Server error {e.resp.status}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

    print(f"\n  [{account_name}] ✓ Upload complete!")
    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  [{account_name}] URL: {url}")

    return {
        "account": account_name,
        "video_id": video_id,
        "url": url,
        "title": title,
    }


def upload_to_all_accounts(
    account_names: list[str],
    video_path: str,
    title: str,
    description: str,
    tags: list[str] = None,
    privacy_status: str = "public",
) -> list[dict]:
    """
    Uploads the same video to multiple YouTube accounts sequentially.

    Args:
        account_names: List of account labels (must match credentials files).
        video_path:    Path to the video file.
        title:         Video title.
        description:   Video description.
        tags:          Optional list of tags.
        privacy_status: "public", "unlisted", or "private".

    Returns:
        List of result dicts from each upload.
    """
    results = []
    failed = []

    for account_name in account_names:
        try:
            result = upload_video(
                account_name=account_name,
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy_status,
            )
            results.append(result)
        except Exception as e:
            print(f"\n  [{account_name}] ✗ Upload FAILED: {e}")
            failed.append({"account": account_name, "error": str(e)})

    if failed:
        print(f"\n[YouTube] Warning: {len(failed)} account(s) failed to upload.")
        for f in failed:
            print(f"  - {f['account']}: {f['error']}")

    return results
