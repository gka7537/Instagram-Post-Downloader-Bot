import os
import shutil
import instaloader
import yt_dlp

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

    if ig_username and ig_password:
        session_file = f"session-{ig_username}"
        try:
            if os.path.exists(session_file):
                L.load_session_from_file(ig_username, session_file)
            else:
                L.login(ig_username, ig_password)
                L.save_session_to_file(ig_username)
        except Exception as e:
            try:
                L.login(ig_username, ig_password)
                L.save_session_to_file(ig_username)
            except Exception as login_err:
                raise Exception(f"Instagram Login Failed: {str(login_err)}")
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
                
            return True, "2FA Login Successful & Session Saved!"
        else:
            L = instaloader.Instaloader()
            if os.path.exists(session_file):
                try:
                    L.load_session_from_file(username)
                    return True, "Session loaded successfully!"
                except Exception:
                    pass

            L.login(username, password)
            L.save_session_to_file(username)
            return True, "Login Successful & Session Saved!"
            
    except instaloader.TwoFactorAuthRequiredException:
        TEMP_LOGIN_SESSIONS[username] = L
        return "2FA_REQUIRED", "🔐 Two-Factor Authentication (2FA) is enabled. Please enter your 6-digit code:"
    except instaloader.BadCredentialsException:
        if username in TEMP_LOGIN_SESSIONS:
            del TEMP_LOGIN_SESSIONS[username]
        return False, "❌ Wrong username or password! Please check your details and try /login again."
    except Exception as e:
        if username in TEMP_LOGIN_SESSIONS:
            del TEMP_LOGIN_SESSIONS[username]
        error_msg = str(e).lower()
        if "challenge" in error_msg or "checkpoint" in error_msg or "susicious" in error_msg or "login attempt" in error_msg:
            return "CHALLENGE_REQUIRED", (
                "⚠️ **Instagram Security Block (New Location/IP Detection)!**\n"
                "इंस्टाग्राम को लगता है कि यह लॉगिन किसी नई जगह से हो रहा है।\n\n"
                "👉 **क्या करें:**\n"
                "1. अपने फोन में आधिकारिक Instagram ऐप खोलें।\n"
                "2. अगर 'It was me' (यह मैं ही हूँ) का ऑप्शन आए तो उसपर क्लिक करें।\n"
                "3. इसके बाद यहाँ दोबारा `/login` से प्रयास करें।"
            )
        return False, f"❌ Login Failed: {str(e)}"

def get_profile_stats(username: str, ig_username: str = None, ig_password: str = None) -> dict:
    L = instaloader.Instaloader(
        download_videos=False, download_pictures=False, download_geotags=False, download_comments=False, save_metadata=False
    )
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

def download_single_link(url_or_shortcode: str) -> tuple:
    """
    yt-dlp का उपयोग करके बिना किसी लॉगिन के सीधे पब्लिक पोस्ट या रील का वीडियो/तस्वीर डाउनलोड करता है।
    """
    if "instagram.com" not in url_or_shortcode:
        clean_input = url_or_shortcode.strip("/")
        url = f"https://www.instagram.com/p/{clean_input}/"
    else:
        url = url_or_shortcode.split("?")[0]

    target_dir = "ytdlp_downloads"
    if os.path.exists(target_dir): 
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    ydl_opts = {
        'outtmpl': os.path.join(target_dir, '%(id)s.%(ext)s'),
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        raise Exception(f"Download failed: {str(e)}")

    files = []
    for root, _, filenames in os.walk(target_dir):
        for f in filenames:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.webm')):
                files.append(os.path.join(root, f))
                
    if not files:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        raise Exception("No media found or link is private/expired.")

    return files, target_dir

def get_highlights_list(username: str, ig_username: str = None, ig_password: str = None):
    if not ig_username or not ig_password:
        raise Exception("Instagram login is mandatory to view highlights. Please login first using /login.")
    
    L = _get_logged_in_loader(ig_username, ig_password)
    clean_username = username.split("?")[0].strip("/").split("/")[-1].replace("@", "")
    profile = instaloader.Profile.from_username(L.context, clean_username)
    highlights = list(L.get_highlights(profile))
    return [{"title": h.title, "id": str(h.unique_id) if hasattr(h, 'unique_id') else h.title} for h in highlights]

def download_specific_highlight(username: str, highlight_title: str, ig_username: str = None, ig_password: str = None) -> tuple:
    if not ig_username or not ig_password:
        raise Exception("Instagram login is mandatory to download highlights. Please login first using /login.")

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
    if not ig_username or not ig_password:
        raise Exception("Instagram login is mandatory to download highlights. Please login first using /login.")

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
        raise Exception("Invalid Highlight link! Please send a valid Instagram Highlight link.")

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
    if not ig_username or not ig_password:
        raise Exception("Instagram login is mandatory to download stories. Please login first using /login.")

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
    if not ig_username or not ig_password:
        raise Exception("Instagram login is mandatory to download stories. Please login first using /login.")

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
            raise Exception("Invalid Story link! Please send a valid Instagram Story link.")

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
            raise Exception("This story has expired or is not public.")

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
        raise Exception(f"Unable to download story: {str(e)}")
        
