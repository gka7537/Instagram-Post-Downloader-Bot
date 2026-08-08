import os
import ssl
import shutil
import glob
import uuid
import certifi
from pathlib import Path
import instaloader
import yt_dlp

# ── SSL & CA Certs Fix (Railway/Render एनवायरनमेंट के लिए) ──────────────────
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['PYTHONHTTPSVERIFY'] = '0'
_orig_ssl_ctx = ssl.create_default_context
def _patched_ssl_ctx(*args, **kwargs):
    kwargs.setdefault('cafile', certifi.where())
    return _orig_ssl_ctx(*args, **kwargs)
ssl.create_default_context = _patched_ssl_ctx

# ── Constants & Cookies File Setup ───────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
COOKIES_FILE = BASE_DIR / "cookies.txt"

# 2FA स्टेट को सुरक्षित रखने के लिए ग्लोबल डिक्शनरी
TEMP_LOGIN_SESSIONS = {}

def _get_logged_in_loader(ig_username: str = None, ig_password: str = None):
    L = instaloader.Instaloader(
        download_videos=True,
        download_pictures=True,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )

    # ── यहाँ cookies.txt का सपोर्ट जोड़ दिया गया है (बिना पुराना कोड हटाए) ──
    if COOKIES_FILE.exists():
        try:
            L.context.load_session_from_file("cookies", str(COOKIES_FILE))
        except Exception:
            pass

    if ig_username and ig_password:
        session_file = f"session-{ig_username}"
        try:
            if os.path.exists(session_file):
                L.load_session_from_file(ig_username, session_file)
            else:
                L.context.user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 293.0.33.108"
                L.login(ig_username, ig_password)
                L.save_session_to_file(ig_username)
        except Exception as e:
            try:
                L.context.user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 293.0.33.108"
                L.login(ig_username, ig_password)
                L.save_session_to_file(ig_username)
            except Exception as login_err:
                raise Exception(f"Instagram Login Failed / इंस्टाग्राम लॉगिन विफल: {str(login_err)}")
    return L

def interactive_instagram_login(username: str, password: str, verification_code: str = None) -> tuple:
    """
    यूज़रनेम, पासवर्ड, 2FA और नई जगह से लॉगिन पर आने वाले सिक्योरिटी ब्लॉक्स को हैंडल करता है।
    """
    session_file = f"session-{username}"

    try:
        if verification_code:
            L = TEMP_LOGIN_SESSIONS.get(username)
            if not L:
                L = instaloader.Instaloader()
                if os.path.exists(session_file):
                    L.load_session_from_file(username)
                else:
                    L.login(username, password)
            
            L.two_factor_login(verification_code)
            L.save_session_to_file(username)
            
            if username in TEMP_LOGIN_SESSIONS:
                del TEMP_LOGIN_SESSIONS[username]
                
            return True, "2FA Login Successful & Session Saved! / 2FA लॉगिन सफल और सेशन सुरक्षित हो गया है!"
        else:
            L = instaloader.Instaloader()
            if os.path.exists(session_file):
                try:
                    L.load_session_from_file(username)
                    return True, "Session loaded successfully! / सेशन सफलतापूर्वक लोड हो गया!"
                except Exception:
                    pass

            L.login(username, password)
            L.save_session_to_file(username)
            return True, "Login Successful & Session Saved! / लॉगिन सफल और सेशन सुरक्षित हो गया है!"
            
    except instaloader.TwoFactorAuthRequiredException:
        TEMP_LOGIN_SESSIONS[username] = L
        return "2FA_REQUIRED", "🔐 Two-Factor Authentication (2FA) is enabled. Please enter your 6-digit code:\n🔐 टू-फैक्टर ऑथेंटिकेशन (2FA) चालू है। कृपया अपना 6-अंकों का कोड दर्ज करें:"
    except instaloader.BadCredentialsException:
        if username in TEMP_LOGIN_SESSIONS:
            del TEMP_LOGIN_SESSIONS[username]
        return False, "❌ Wrong username/password! Please check details and try /login again.\n❌ गलत यूज़रनेम या पासवर्ड! कृपया जांच करें और दोबारा /login करें।"
    except Exception as e:
        if username in TEMP_LOGIN_SESSIONS:
            del TEMP_LOGIN_SESSIONS[username]
        error_msg = str(e).lower()
        if "challenge" in error_msg or "checkpoint" in error_msg or "susicious" in error_msg or "login attempt" in error_msg:
            return "CHALLENGE_REQUIRED", (
                "⚠️ **Instagram Security Block (New Location/IP Detection)!**\n"
                "⚠️ **इंस्टाग्राम सिक्योरिटी ब्लॉक (नई लोकेशन/IP का पता चला)!**\n\n"
                "इंस्टाग्राम को लगता है कि यह लॉगिन किसी नई जगह से हो रहा है / Instagram thinks this login is from a new location.\n\n"
                "👉 **क्या करें / What to do:**\n"
                "1. अपने फोन में आधिकारिक Instagram ऐप खोलें / Open official Instagram app.\n"
                "2. अगर 'It was me' (यह मैं ही हूँ) का ऑप्शन आए तो उसपर क्लिक करें / Click 'It was me' if it appears.\n"
                "3. इसके बाद यहाँ दोबारा `/login` से प्रयास करें या इसके बजाय **Cookies.txt** विकल्प का चयन करें।"
            )
        return False, f"❌ Login Failed / लॉगिन विफल: {str(e)}"

def get_profile_stats(username: str, ig_username: str = None, ig_password: str = None) -> dict:
    L = instaloader.Instaloader(
        download_videos=False, download_pictures=False, download_geotags=False, download_comments=False, save_metadata=False
    )
    if COOKIES_FILE.exists():
        try:
            L.context.load_session_from_file("cookies", str(COOKIES_FILE))
        except Exception:
            pass

    if ig_username and ig_password:
        try: 
            L = _get_logged_in_loader(ig_username, ig_password)
        except: 
            pass

    clean_username = username.split("?")[0].strip("/").split("/")[-1].replace("@", "")
    profile = instaloader.Profile.from_username(L.context, clean_username)
    return {
        "username": profile.username,
        "total_posts": profile.mediacount,
        "is_private": profile.is_private
    }

def download_specific_content(username: str, start_idx: int, end_idx: int, ig_username: str = None, ig_password: str = None) -> tuple:
    if ig_username and ig_password:
        try:
            L = _get_logged_in_loader(ig_username, ig_password)
        except:
            L = instaloader.Instaloader(download_videos=True, download_pictures=True, save_metadata=False, compress_json=False)
    else:
        L = instaloader.Instaloader(download_videos=True, download_pictures=True, save_metadata=False, compress_json=False)
        if COOKIES_FILE.exists():
            try:
                L.context.load_session_from_file("cookies", str(COOKIES_FILE))
            except Exception:
                pass

    clean_username = username.split("?")[0].strip("/").split("/")[-1].replace("@", "")
    target_dir = f"temp_{clean_username}_posts"
    if os.path.exists(target_dir): shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    profile = instaloader.Profile.from_username(L.context, clean_username)
    count = 0
    iterator = profile.get_posts()

    for idx, post in enumerate(iterator, start=1):
        if start_idx <= idx <= end_idx:
            try:
                L.download_post(post, target=target_dir)
                count += 1
            except:
                pass
        if idx > end_idx:
            break

    if count == 0:
        shutil.rmtree(target_dir, ignore_errors=True)
        return None, 0

    zip_filename = f"{clean_username}_posts_{start_idx}_to_{end_idx}"
    shutil.make_archive(zip_filename, 'zip', target_dir)
    shutil.rmtree(target_dir, ignore_errors=True)
    return f"{zip_filename}.zip", count

def download_single_link(url_or_shortcode: str, ig_username: str = None, ig_password: str = None) -> tuple:
    """
    पहले yt-dlp से स्मार्ट ऑप्शन (हेडर्स, स्लीप और Cookies.txt सपोर्ट) के साथ कोशिश करता है। 
    अगर फेल हो जाए या मल्टी-इमेज (फोटो+वीडियो) हो, तो instaloader का उपयोग करता है।
    """
    if "instagram.com" not in url_or_shortcode:
        clean_input = url_or_shortcode.strip("/")
        url = f"https://www.instagram.com/p/{clean_input}/"
        shortcode = clean_input
    else:
        url = url_or_shortcode.split("?")[0]
        clean_input = url.strip("/")
        parts = clean_input.split("/")
        if "p" in parts:
            shortcode = parts[parts.index("p") + 1]
        elif "reel" in parts:
            shortcode = parts[parts.index("reel") + 1]
        else:
            shortcode = clean_input.split("/")[-1]

    target_dir = f"single_{shortcode}"
    if os.path.exists(target_dir): 
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    success_download = False

    # 1. Smart yt-dlp Options & Block-proof Headers + Cookies Integration
    ydl_opts = {
        'outtmpl': os.path.join(target_dir, '%(id)s.%(ext)s'),
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': '*/*',
        },
        'sleep_interval': 1,
        'max_sleep_interval': 3,
        'nocheckcertificate': True,
    }

    # अगर cookies.txt फाइल मौजूद है, तो उसे ऑटोमैटिकली लोड करेगा
    if COOKIES_FILE.exists():
        ydl_opts['cookiefile'] = str(COOKIES_FILE)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        success_download = True
    except Exception:
        pass

    # 2. अगर yt-dlp फेल हो जाए (जैसे फोटो+वीडियो एल्बम होने पर), तो cookies.txt के साथ instaloader का उपयोग करेंगे
    if not success_download:
        try:
            # ── यहाँ सुनिश्चित किया गया है कि instaloader हमेशा _get_logged_in_loader का उपयोग करे या कुकीज़ लोड करे ──
            if ig_username and ig_password:
                L = _get_logged_in_loader(ig_username, ig_password)
            else:
                L = instaloader.Instaloader(
                    download_videos=True, download_pictures=True, 
                    download_geotags=False, download_comments=False, 
                    save_metadata=False, compress_json=False
                )
                if COOKIES_FILE.exists():
                    try:
                        L.context.load_session_from_file("cookies", str(COOKIES_FILE))
                    except Exception:
                        pass

            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=target_dir)
            success_download = True
        except Exception as e:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise Exception(f"Download failed / डाउनलोड विफल: {str(e)}")

    files = []
    for root, _, filenames in os.walk(target_dir):
        for f in filenames:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.webm')):
                files.append(os.path.join(root, f))
                
    if not files:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        raise Exception("No media found or link is private/expired. / कोई मीडिया नहीं मिला या लिंक प्राइवेट/एक्सपायर है।")

    return files, target_dir

def get_highlights_list(username: str, ig_username: str = None, ig_password: str = None):
    # ── यहाँ चेक को फ्लेक्सिबल बनाया गया है ताकि cookies होने पर भी हाइलाइट्स लोड हो सकें ──
    if (not ig_username or not ig_password) and not COOKIES_FILE.exists():
        raise Exception("❌ बिना लॉगिन या कुकीज़ के हाइलाइट नहीं देखा जा सकता! पहले /login करें या cookies.txt अपलोड करें।\n❌ Instagram login or cookies file is mandatory to view highlights.")
    
    L = _get_logged_in_loader(ig_username, ig_password)
    clean_username = username.split("?")[0].strip("/").split("/")[-1].replace("@", "")
    profile = instaloader.Profile.from_username(L.context, clean_username)
    highlights = list(L.get_highlights(profile))
    return [{"title": h.title, "id": str(h.unique_id) if hasattr(h, 'unique_id') else h.title} for h in highlights]

def download_specific_highlight(username: str, highlight_title: str, ig_username: str = None, ig_password: str = None) -> tuple:
    if (not ig_username or not ig_password) and not COOKIES_FILE.exists():
        raise Exception("❌ बिना लॉगिन या कुकीज़ के हाइलाइट डाउनलोड नहीं हो सकता! पहले /login करें या cookies.txt अपलोड करें।\n❌ Instagram login or cookies file is mandatory to download highlights.")

    L = _get_logged_in_loader(ig_username, ig_password)
    clean_username = username.split("?")[0].strip("/").split("/")[-1].replace("@", "")
    target_dir = f"highlight_{clean_username}_{highlight_title}"
    if os.path.exists(target_dir): shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    profile = instaloader.Profile.from_username(L.context, clean_username)
    count = 0
    for highlight in L.get_highlights(profile):
        if highlight.title.strip().lower() == highlight_title.strip().lower():
            for item in highlight.getItems():
                try:
                    L.download_post(item, target=target_dir)
                    count += 1
                except: pass
            break

    if count == 0:
        shutil.rmtree(target_dir, ignore_errors=True)
        return None, 0

    zip_filename = f"{clean_username}_{highlight_title}"
    shutil.make_archive(zip_filename, 'zip', target_dir)
    shutil.rmtree(target_dir, ignore_errors=True)
    return f"{zip_filename}.zip", count

def download_highlight_by_link(url: str, ig_username: str = None, ig_password: str = None) -> tuple:
    if (not ig_username or not ig_password) and not COOKIES_FILE.exists():
        raise Exception("❌ बिना लॉगिन या कुकीज़ के हाइलाइट डाउनलोड नहीं हो सकता! पहले /login करें या cookies.txt अपलोड करें।\n❌ Instagram login or cookies file is mandatory to download highlights.")

    L = _get_logged_in_loader(ig_username, ig_password)
    target_dir = "highlight_direct"
    if os.path.exists(target_dir): shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    clean_url = url.split("?")[0]
    parts = clean_url.strip("/").split("/")
    highlight_id = None
    for i, part in enumerate(parts):
        if part == "highlights" and i + 1 < len(parts):
            highlight_id = parts[i + 1]
            break

    if not highlight_id:
        raise Exception("Invalid Highlight link! Please send a valid Instagram Highlight link.\nअमान्य हाइलाइट लिंक! कृपया एक सही इंस्टाग्राम हाइलाइट लिंक भेजें।")

    highlight = instaloader.Highlight(L.context, int(highlight_id))
    count = 0
    for item in highlight.getItems():
        try:
            L.download_post(item, target=target_dir)
            count += 1
        except: pass

    zip_filename = f"highlight_{highlight_id}"
    shutil.make_archive(zip_filename, 'zip', target_dir)
    shutil.rmtree(target_dir, ignore_errors=True)
    return f"{zip_filename}.zip", count

def download_user_stories(username: str, ig_username: str = None, ig_password: str = None) -> tuple:
    if (not ig_username or not ig_password) and not COOKIES_FILE.exists():
        raise Exception("❌ बिना लॉगिन या कुकीज़ के स्टोरी डाउनलोड नहीं हो सकती! पहले /login करें या cookies.txt अपलोड करें।\n❌ Instagram login or cookies file is mandatory to download stories.")

    L = _get_logged_in_loader(ig_username, ig_password)
    clean_username = username.split("?")[0].strip("/").split("/")[-1].replace("@", "")
    target_dir = f"stories_{clean_username}"
    if os.path.exists(target_dir): shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    profile = instaloader.Profile.from_username(L.context, clean_username)
    for story in L.get_stories([profile.userid]):
        for item in story.getItems():
            try: L.download_post(item, target=target_dir)
            except: pass

    files = []
    for root, _, filenames in os.walk(target_dir):
        for f in filenames:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov')):
                files.append(os.path.join(root, f))
    files.sort()
    return files, target_dir

def download_story_by_link(url: str, ig_username: str = None, ig_password: str = None) -> tuple:
    if (not ig_username or not ig_password) and not COOKIES_FILE.exists():
        raiseException("❌ बिना लॉगिन या कुकीज़ के स्टोरी डाउनलोड नहीं हो सकती! पहले /login करें या cookies.txt अपलोड करें।\n❌ Instagram login or cookies file is mandatory to download stories.")

    L = _get_logged_in_loader(ig_username, ig_password)
    target_dir = "story_direct"
    if os.path.exists(target_dir): shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    try:
        clean_url = url.split("?")[0]
        parts = clean_url.strip("/").split("/")
        
        story_media_id = None
        target_username = None
        
        for i, part in enumerate(parts):
            if part == "stories" and i + 1 < len(parts):
                target_username = parts[i + 1]
            if part == "stories" and i + 2 < len(parts):
                story_media_id = parts[i + 2]
                break

        if not story_media_id or not target_username:
            raise Exception("Invalid Story link! Please send a valid Instagram Story link.\nअमान्य हाइलाइट लिंक! कृपया एक सही इंस्टाग्राम हाइलाइट लिंक भेजें।")

        profile = instaloader.Profile.from_username(L.context, target_username)
        downloaded = False

        for story in L.get_stories([profile.userid]):
            for item in story.getItems():
                if str(item.mediaid) == str(story_media_id):
                    L.download_post(item, target=target_dir)
                    downloaded = True
                    break
            if downloaded:
                break

        if not downloaded:
            raise Exception("This story has expired or is not public.\nयह स्टोरी एक्सपायर हो चुकी है या पब्लिक नहीं है।")

        files = []
        for root, _, filenames in os.walk(target_dir):
            for f in filenames:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov')):
                    files.append(os.path.join(root, f))
        files.sort()
        return files, target_dir
    except Exception as e:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        raise Exception(f"Unable to download story / स्टोरी डाउनलोड करने में असमर्थ: {str(e)}")
        
