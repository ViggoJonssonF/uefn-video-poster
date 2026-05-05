"""
UEFN Video Poster — Web Frontend
Streamlit app for posting short-form videos to YouTube and TikTok.
"""

import streamlit as st
import base64
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UEFN Video Poster",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password login gate ───────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("## 🎮 UEFN Video Poster")
    st.markdown("Enter the password to access the app.")
    with st.form("login_form"):
        pw = st.text_input("Password", type="password")
        login = st.form_submit_button("Log in", type="primary")
        if login:
            if pw == st.secrets.get("app_password", ""):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ── Credentials dir (same location the uploaders expect) ─────────────────────
CRED_DIR = Path(__file__).parent / "credentials"
CRED_DIR.mkdir(exist_ok=True)


@st.cache_resource
def init_credentials():
    """
    Decode credentials from Streamlit secrets and write to the credentials folder.
    Runs once per app session (cached).
    """
    try:
        # YouTube client secrets — same file for all 3 accounts
        yt_secrets = st.secrets["youtube_secrets"]
        for account in ["account1", "account2", "account3"]:
            (CRED_DIR / f"youtube_secrets_{account}.json").write_text(yt_secrets)

        # YouTube OAuth tokens — stored as base64-encoded pickle
        for account in ["account1", "account2", "account3"]:
            key = f"youtube_token_{account}"
            if key in st.secrets:
                token_bytes = base64.b64decode(st.secrets[key])
                (CRED_DIR / f"youtube_token_{account}.pkl").write_bytes(token_bytes)

        # TikTok app config
        (CRED_DIR / "tiktok_config.json").write_text(st.secrets["tiktok_config"])

        # TikTok OAuth token
        if "tiktok_token" in st.secrets:
            (CRED_DIR / "tiktok_token.json").write_text(st.secrets["tiktok_token"])

        return True, None
    except Exception as e:
        return False, str(e)


ok, err = init_credentials()

# ── Load persistent history from Google Sheets (once per session) ─────────────
if "history" not in st.session_state:
    try:
        from sheets_logger import load_history
        st.session_state.history = load_history()
    except Exception:
        st.session_state.history = []

# ── Session state ─────────────────────────────────────────────────────────────
if "queue" not in st.session_state:
    st.session_state.queue = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎮 UEFN Video Poster")
    st.caption("Post to all accounts in one click.")
    if st.button("🔒 Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()

    if not ok:
        st.error(f"⚠️ Credentials error:\n{err}")
    else:
        st.success("✅ All credentials loaded")

    st.divider()
    st.subheader("📋 Recent Posts")
    if not st.session_state.history:
        st.caption("No posts yet.")
    else:
        for h in reversed(st.session_state.history[-15:]):
            date_str = h.get("date", "")
            time_str = h.get("time", "")
            stamp = f"{date_str} {time_str}".strip() if date_str else time_str
            st.caption(f"**{h['title'][:28]}**")
            st.caption(f"🕐 {stamp}")
            st.caption(f"📤 {h['platforms']}")
            st.divider()

# Stop here if credentials failed
if not ok:
    st.error("Credentials could not be loaded from Streamlit secrets. See sidebar for details.")
    st.stop()

# ── Main layout ───────────────────────────────────────────────────────────────
st.header("Add Video to Queue")

with st.form("upload_form", clear_on_submit=True):
    video_file = st.file_uploader(
        "Drag & drop your video here",
        type=["mp4", "mov", "avi"],
        help="MP4 recommended. Max 200MB.",
    )

    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input(
            "Title / TikTok Caption *",
            placeholder="Check out my Robbery Bob map! 🎮 #fortnite #uefn",
        )
    with col2:
        privacy = st.selectbox("Privacy", ["Public", "Private", "Unlisted"])

    description = st.text_area(
        "YouTube Description",
        placeholder="Play my Fortnite map! Code: XXXX-XXXX-XXXX\n\n#uefn #fortnite #gaming",
        height=100,
    )

    tags = st.text_input(
        "YouTube Tags (comma-separated)",
        placeholder="fortnite, uefn, robbery bob, gaming, creative",
    )

    st.write("**Post to:**")
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        use_yt1 = st.checkbox("YouTube #1", value=True)
    with pc2:
        use_yt2 = st.checkbox("YouTube #2", value=True)
    with pc3:
        use_yt3 = st.checkbox("YouTube #3", value=True)
    with pc4:
        use_tt = st.checkbox("TikTok", value=True)

    submitted = st.form_submit_button("➕ Add to Queue", type="primary")

    if submitted:
        if not video_file:
            st.error("Please upload a video file.")
        elif not title:
            st.error("Please enter a title.")
        else:
            item = {
                "id": str(uuid.uuid4())[:8],
                "video_bytes": video_file.read(),
                "video_name": video_file.name,
                "title": title,
                "description": description or title,
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
                "privacy": privacy.lower(),
                "platforms": {
                    "account1": use_yt1,
                    "account2": use_yt2,
                    "account3": use_yt3,
                    "tiktok": use_tt,
                },
                "status": "pending",
                "results": [],
                "added_at": datetime.now().strftime("%H:%M:%S"),
            }
            st.session_state.queue.append(item)
            st.success(f"✅ **{title[:50]}** added to queue!")

# ── Queue ─────────────────────────────────────────────────────────────────────
st.divider()
pending_count = sum(1 for x in st.session_state.queue if x["status"] == "pending")
st.header(f"Queue — {len(st.session_state.queue)} item(s), {pending_count} pending")

if not st.session_state.queue:
    st.info("Queue is empty. Add a video above to get started.")
else:
    # Post All button
    if pending_count > 0:
        if st.button("🚀 Post All Pending", type="primary"):
            for item in st.session_state.queue:
                if item["status"] != "pending":
                    continue

                item["status"] = "uploading"
                accounts = [k for k, v in item["platforms"].items() if v and k != "tiktok"]
                do_tiktok = item["platforms"].get("tiktok", False)

                with st.status(f"📤 Posting **{item['title'][:40]}**...", expanded=True) as s:
                    # Write video to a temp file
                    suffix = Path(item["video_name"]).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(item["video_bytes"])
                        tmp_path = tmp.name

                    any_success = False

                    # ── YouTube (each account isolated) ───────────────────────
                    if accounts:
                        st.write(f"Uploading to YouTube ({', '.join(accounts)})...")
                        try:
                            from youtube_uploader import upload_to_all_accounts
                            yt_results = upload_to_all_accounts(
                                account_names=accounts,
                                video_path=tmp_path,
                                title=item["title"],
                                description=item["description"],
                                tags=item["tags"],
                                privacy_status=item["privacy"],
                            )
                            item["results"].extend(yt_results)
                            for r in yt_results:
                                if "error" in r:
                                    st.error(f"❌ {r['account']}: {r['error']}")
                                else:
                                    any_success = True
                                    st.write(f"✅ YouTube {r['account']}: {r['url']}")
                        except Exception as yt_err:
                            item["results"].append({"error": str(yt_err), "platform": "youtube"})
                            st.error(f"❌ YouTube error: {yt_err}")

                    # ── TikTok (isolated so YouTube success still logs) ────────
                    if do_tiktok:
                        st.write("Uploading to TikTok...")
                        try:
                            tiktok_privacy_map = {
                                "public": "PUBLIC_TO_EVERYONE",
                                "unlisted": "MUTUAL_FOLLOW_FRIENDS",
                                "private": "SELF_ONLY",
                            }
                            from tiktok_uploader import upload_video as tiktok_upload
                            tt_result = tiktok_upload(
                                video_path=tmp_path,
                                title=item["title"],
                                description=item["description"],
                                privacy_level=tiktok_privacy_map.get(item["privacy"], "SELF_ONLY"),
                            )
                            item["results"].append(tt_result)
                            any_success = True
                            st.write(f"✅ TikTok: {tt_result.get('status')}")
                        except Exception as tt_err:
                            item["results"].append({"error": str(tt_err), "platform": "tiktok"})
                            st.error(f"❌ TikTok error: {tt_err}")

                    # ── Determine overall status ───────────────────────────────
                    all_failed = not any_success
                    item["status"] = "failed" if all_failed else "done"
                    if all_failed:
                        s.update(label=f"❌ Failed — {item['title'][:40]}", state="error")
                    else:
                        s.update(label=f"✅ Done — {item['title'][:40]}", state="complete")

                    # ── Log to Google Sheets whenever at least one platform succeeded ──
                    if not all_failed:
                        platforms_str = ", ".join(
                            (["YT " + k for k, v in item["platforms"].items() if v and k != "tiktok"])
                            + (["TikTok"] if do_tiktok else [])
                        )
                        history_entry = {
                            "title": item["title"],
                            "time": datetime.now().strftime("%H:%M"),
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "platforms": platforms_str,
                            "privacy": item["privacy"],
                        }
                        st.session_state.history.append(history_entry)

                        try:
                            from sheets_logger import log_post
                            logged = log_post(
                                title=item["title"],
                                platforms=platforms_str,
                                privacy=item["privacy"],
                                results=item["results"],
                            )
                            if logged:
                                st.write("📊 Logged to Google Sheets")
                            else:
                                st.warning("⚠️ Sheets logging skipped (check secrets or sheet sharing)")
                        except Exception as sheets_err:
                            st.warning(f"⚠️ Sheets logging failed: {sheets_err}")
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

            st.rerun()

    # Clear completed button
    done_count = sum(1 for x in st.session_state.queue if x["status"] in ("done", "failed"))
    if done_count > 0:
        if st.button(f"🗑️ Clear {done_count} finished item(s)"):
            st.session_state.queue = [x for x in st.session_state.queue if x["status"] not in ("done", "failed")]
            st.rerun()

    st.write("")

    # Queue item display
    status_icons = {"pending": "⏳", "uploading": "🔄", "done": "✅", "failed": "❌"}

    for i, item in enumerate(st.session_state.queue):
        icon = status_icons.get(item["status"], "⏳")
        platforms = []
        for k, v in item["platforms"].items():
            if v:
                platforms.append("TikTok" if k == "tiktok" else f"YT {k}")

        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{icon} {item['title'][:60]}**")
                st.caption(
                    f"📁 {item['video_name']}  ·  "
                    f"🔒 {item['privacy'].title()}  ·  "
                    f"📤 {', '.join(platforms)}  ·  "
                    f"⏰ Added {item['added_at']}  ·  "
                    f"Status: `{item['status']}`"
                )
                for r in item["results"]:
                    if "error" in r:
                        st.error(f"❌ {r.get('account') or r.get('platform', '?')}: {r['error'][:100]}")
                    elif r.get("platform") == "tiktok":
                        st.success(f"✅ TikTok — {r.get('status', 'posted')}")
                    elif "url" in r:
                        st.success(f"✅ YouTube {r.get('account')} — [View video]({r['url']})")
            with c2:
                if item["status"] == "pending":
                    if st.button("🗑️ Remove", key=f"rm_{item['id']}"):
                        st.session_state.queue.pop(i)
                        st.rerun()
