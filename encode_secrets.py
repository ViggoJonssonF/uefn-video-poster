"""
encode_secrets.py
=================
Run this ONCE on your local machine to generate the values you need to paste
into Streamlit Community Cloud's secrets manager.

Usage:
    python encode_secrets.py

Copy the entire output and paste it into:
Streamlit Community Cloud → your app → Settings → Secrets
"""

import base64
import json
from pathlib import Path

CREDS = Path(__file__).parent.parent / "video_poster" / "credentials"

output_lines = []

# YouTube secrets (same file for all accounts — just encode once)
secrets_file = CREDS / "youtube_secrets_account1.json"
if secrets_file.exists():
    content = secrets_file.read_text()
    # Validate it's valid JSON
    json.loads(content)
    # Store as raw JSON string (no encoding needed for text)
    output_lines.append('youtube_secrets = """')
    output_lines.append(content)
    output_lines.append('"""')
    output_lines.append("")
    print(f"✓ youtube_secrets")
else:
    print(f"✗ Missing: {secrets_file}")

# YouTube tokens (binary pickle files — need base64 encoding)
for account in ["account1", "account2", "account3"]:
    token_file = CREDS / f"youtube_token_{account}.pkl"
    if token_file.exists():
        token_b64 = base64.b64encode(token_file.read_bytes()).decode()
        output_lines.append(f'youtube_token_{account} = "{token_b64}"')
        output_lines.append("")
        print(f"✓ youtube_token_{account}")
    else:
        print(f"✗ Missing: {token_file.name} (run setup_credentials.py first)")

# TikTok config
tiktok_config = CREDS / "tiktok_config.json"
if tiktok_config.exists():
    content = tiktok_config.read_text()
    json.loads(content)
    output_lines.append('tiktok_config = """')
    output_lines.append(content)
    output_lines.append('"""')
    output_lines.append("")
    print(f"✓ tiktok_config")
else:
    print(f"✗ Missing: {tiktok_config}")

# TikTok token
tiktok_token = CREDS / "tiktok_token.json"
if tiktok_token.exists():
    content = tiktok_token.read_text()
    json.loads(content)
    output_lines.append('tiktok_token = """')
    output_lines.append(content)
    output_lines.append('"""')
    output_lines.append("")
    print(f"✓ tiktok_token")
else:
    print(f"✗ Missing: {tiktok_token}")

print("\n" + "=" * 60)
print("PASTE THE FOLLOWING INTO STREAMLIT SECRETS:")
print("=" * 60)
print("\n".join(output_lines))
print("=" * 60)
