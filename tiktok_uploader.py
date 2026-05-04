"""
tiktok_uploader.py
Handles OAuth authentication and video uploads using the TikTok Content Posting API v2.
Stores tokens in ./credentials/tiktok_token.json.

TikTok API docs: https://developers.tiktok.com/doc/content-posting-api-get-started
Required scope: video.publish
"""

import os
import json
import math
import time
import webbrowser
import urllib.parse
from pathlib import Path

import requests  # noqa: E402

CREDENTIALS_DIR = Path(__file__).parent / "credentials"
TOKEN_FILE = CREDENTIALS_DIR / "tiktok_token.json"
CONFIG_FILE = CREDENTIALS_DIR / "tiktok_config.json"

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
TIKTOK_UPLOAD_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

# Max chunk size: 64 MB (TikTok supports up to 64 MB per chunk)
MAX_CHUNK_SIZE = 64 * 1024 * 1024
# Recommended chunk size for most videos
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024

# TikTok does not allow localhost redirect URIs.
# We use the GitHub Pages URL — after authorizing, the browser will land on a
# 404 page. That's fine! Just copy the full URL from the address bar and paste it.
REDIRECT_URI = "https://viggojonssonf.github.io/callback"


# --- Token management ---

def load_config() -> dict:
    """Load TikTok app credentials (client_key, client_secret)."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"TikTok config file not found: {CONFIG_FILE}\n"
            "Please follow the SETUP_GUIDE.md to create this file with your "
            "client_key and client_secret from the TikTok Developer Portal."
        )
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_token() -> dict | None:
    """Load the saved TikTok OAuth token, or None if not present."""
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def save_token(token_data: dict):
    """Save TikTok OAuth token to disk."""
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def refresh_access_token(config: dict, token_data: dict) -> dict:
    """Refresh the TikTok access token using the refresh token."""
    print("  [TikTok] Refreshing access token...")
    resp = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": config["client_key"],
        "client_secret": config["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
    })
    resp.raise_for_status()
    new_token = resp.json()
    if "error" in new_token:
        raise RuntimeError(f"Token refresh failed: {new_token}")
    new_token["obtained_at"] = int(time.time())
    save_token(new_token)
    print("  [TikTok] Token refreshed successfully.")
    return new_token


def authorize(config: dict) -> dict:
    """
    Run the OAuth 2.0 authorization flow for TikTok.
    Opens a browser for login. After authorizing, TikTok redirects to a GitHub
    Pages URL that will show a 404 — that's expected. Just copy the full URL
    from the browser address bar and paste it into the terminal.
    """
    params = {
        "client_key": config["client_key"],
        "response_type": "code",
        "scope": "video.publish,user.info.basic",
        "redirect_uri": REDIRECT_URI,
        "state": "tiktok_auth",
    }
    auth_url = TIKTOK_AUTH_URL + "?" + urllib.parse.urlencode(params)

    print(f"\n  [TikTok] Opening browser for TikTok authorization...")
    print(f"  If the browser doesn't open automatically, visit this URL:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("  [TikTok] After you approve the app in the browser, you will be")
    print("  redirected to a page that shows a 404 error. That is expected!")
    print("  Copy the FULL URL from your browser's address bar and paste it below.\n")
    callback_url = input("  Paste the full redirect URL here: ").strip()

    # Parse the authorization code from the pasted URL
    parsed = urllib.parse.urlparse(callback_url)
    params_parsed = urllib.parse.parse_qs(parsed.query)
    if "code" not in params_parsed:
        raise RuntimeError(
            "No authorization code found in the URL. "
            "Make sure you copied the full URL from the address bar after the redirect."
        )
    auth_code = params_parsed["code"][0]

    print("  [TikTok] Authorization code received. Exchanging for tokens...")
    resp = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": config["client_key"],
        "client_secret": config["client_secret"],
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    })
    resp.raise_for_status()
    token_data = resp.json()

    if "error" in token_data:
        raise RuntimeError(f"Token exchange failed: {token_data}")

    token_data["obtained_at"] = int(time.time())
    save_token(token_data)
    print("  [TikTok] Tokens saved successfully.")
    return token_data


def get_valid_token() -> tuple[dict, dict]:
    """
    Returns (config, token_data) with a valid access token.
    Refreshes or re-authorizes as needed.
    """
    config = load_config()
    token_data = load_token()

    if not token_data:
        print("  [TikTok] No saved token found. Starting authorization flow...")
        token_data = authorize(config)
        return config, token_data

    # Check if access token is expired (with 5 min buffer)
    expires_in = token_data.get("expires_in", 86400)
    obtained_at = token_data.get("obtained_at", 0)
    if time.time() > obtained_at + expires_in - 300:
        try:
            token_data = refresh_access_token(config, token_data)
        except Exception:
            print("  [TikTok] Refresh failed. Re-authorizing...")
            token_data = authorize(config)

    return config, token_data


# --- Video upload ---

def upload_video(
    video_path: str,
    title: str,
    description: str,
    privacy_level: str = "PUBLIC_TO_EVERYONE",
    disable_duet: bool = False,
    disable_comment: bool = False,
    disable_stitch: bool = False,
) -> dict:
    """
    Uploads a video to TikTok using the Content Posting API.

    Args:
        video_path:      Path to the video file (mp4 recommended, max 10 min / 4 GB).
        title:           Post caption/title (max 2200 chars, include hashtags here).
        description:     Same as title for TikTok (caption field).
        privacy_level:   "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", or "SELF_ONLY".
        disable_duet:    Disable duets for this video.
        disable_comment: Disable comments for this video.
        disable_stitch:  Disable stitches for this video.

    Returns:
        dict with keys: platform, publish_id, status
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    video_size = video_path.stat().st_size
    # chunk_size must never exceed the actual file size — TikTok rejects the mismatch
    chunk_size = min(DEFAULT_CHUNK_SIZE, video_size)
    total_chunks = math.ceil(video_size / chunk_size)

    print(f"\n[TikTok] Uploading video...")
    print(f"  File: {video_path.name} ({video_size / 1024 / 1024:.1f} MB, {total_chunks} chunk(s))")

    config, token_data = get_valid_token()
    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # Combine title + description into a single caption (TikTok style)
    caption = title if title == description else f"{title}\n\n{description}"
    caption = caption[:2200]

    # Step 1: Initialize the upload
    init_payload = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch": disable_stitch,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }

    print("  [TikTok] Initializing upload...")
    init_resp = requests.post(TIKTOK_UPLOAD_INIT_URL, headers=headers, json=init_payload)
    if not init_resp.ok:
        raise RuntimeError(
            f"TikTok upload init failed (HTTP {init_resp.status_code}):\n{init_resp.text}"
        )
    init_data = init_resp.json()

    if init_data.get("error", {}).get("code", "ok") != "ok":
        raise RuntimeError(f"TikTok upload init failed: {json.dumps(init_data, indent=2)}")

    upload_url = init_data["data"]["upload_url"]
    publish_id = init_data["data"]["publish_id"]
    print(f"  [TikTok] Publish ID: {publish_id}")

    # Step 2: Upload video chunks
    with open(video_path, "rb") as f:
        for chunk_index in range(total_chunks):
            chunk_data = f.read(chunk_size)
            actual_chunk_size = len(chunk_data)
            start_byte = chunk_index * chunk_size
            end_byte = start_byte + actual_chunk_size - 1

            progress = int((chunk_index + 1) / total_chunks * 100)
            print(f"\r  [TikTok] Uploading: {progress}% (chunk {chunk_index + 1}/{total_chunks})", end="", flush=True)

            chunk_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(actual_chunk_size),
                "Content-Range": f"bytes {start_byte}-{end_byte}/{video_size}",
            }

            retry = 0
            while retry < 3:
                chunk_resp = requests.put(upload_url, headers=chunk_headers, data=chunk_data)
                if chunk_resp.status_code in [200, 201, 206]:
                    break
                retry += 1
                time.sleep(2 ** retry)
            else:
                raise RuntimeError(f"Failed to upload chunk {chunk_index + 1}: HTTP {chunk_resp.status_code}")

    print(f"\n  [TikTok] ✓ All chunks uploaded!")

    # Step 3: Poll status until published or failed
    print("  [TikTok] Waiting for TikTok to process the video...")
    status_headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    max_wait = 120  # seconds
    poll_interval = 5
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status_resp = requests.post(TIKTOK_STATUS_URL, headers=status_headers, json={"publish_id": publish_id})
        status_resp.raise_for_status()
        status_data = status_resp.json()

        pub_status = status_data.get("data", {}).get("status", "UNKNOWN")
        print(f"\r  [TikTok] Status: {pub_status} ({elapsed}s elapsed)", end="", flush=True)

        if pub_status == "PUBLISH_COMPLETE":
            print(f"\n  [TikTok] ✓ Video published successfully!")
            return {"platform": "tiktok", "publish_id": publish_id, "status": pub_status}
        elif pub_status in ["FAILED", "CANCELLED"]:
            fail_reason = status_data.get("data", {}).get("fail_reason", "Unknown")
            raise RuntimeError(f"TikTok publish failed: {pub_status} - {fail_reason}")

    print(f"\n  [TikTok] Note: Video is still processing (publish_id: {publish_id}). Check TikTok app.")
    return {"platform": "tiktok", "publish_id": publish_id, "status": "PROCESSING"}
                                                             