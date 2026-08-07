import os
import shutil
import asyncio
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import API_ID, API_HASH, BOT_TOKEN
from downloader import (
    get_highlights_list, download_specific_highlight, download_single_link, 
    download_highlight_by_link, download_user_stories, download_story_by_link, 
    get_profile_stats, download_specific_content, interactive_instagram_login
)

ACTIVE_LOGINS = {}

app = Client(
    "insta_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

USER_STATE = {}

server = Flask(__name__)

@server.route('/')
def home():
    return "🤖 Instagram Downloader Bot is Active and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 1000))
    server.run(host="0.0.0.0", port=port)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    help_text = (
        "🤖 **Instagram Advanced Downloader Bot**\n\n"
        "✨ **कमांड्स:**\n"
        "• `/login` - इंस्टाग्राम अकाउंट लॉगिन करें\n"
        "• `/posts username start end` - पोस्ट्स डाउनलोड करें\n"
        "• `/reels username start end` - रील्स डाउनलोड करें\n"
        "• `/story` - स्टोरी डाउनलोड करें\n"
        "• `/highlight` - हाइलाइट डाउनलोड करें\n"
        "• किसी भी सिंगल पोस्ट/रील का लिंक सीधे भेजें।"
    )
    await message.reply_text(help_text)

@app.on_message(filters.command("login"))
async def login_command(client: Client, message: Message):
    chat_id = message.chat.id
    await message.reply_text("👤 कृपया अपना Instagram **Username** भेजें:")
    USER_STATE[chat_id] = {"step": "waiting_for_ig_username"}

@app.on_message(filters.command("highlight"))
async def highlight_command(client: Client, message: Message):
    chat_id = message.chat.id
    login_data = ACTIVE_LOGINS.get(chat_id)
    if not login_data:
        await message.reply_text("❌ बिना लॉगिन के हाइलाइट डाउनलोड नहीं हो सकता!\n\nकृपया पहले `/login` टाइप करके लॉगिन करें।")
        return
    await message.reply_text("📂 कृपया उस Instagram **यूजरनेम** या **प्रोफाइल लिंक** को भेजें जिसके हाइलाइट्स देखने हैं:")
    USER_STATE[chat_id] = {"step": "waiting_for_username"}

@app.on_message(filters.command("story"))
async def story_command(client: Client, message: Message):
    chat_id = message.chat.id
    login_data = ACTIVE_LOGINS.get(chat_id)
    if not login_data:
        await message.reply_text("❌ बिना लॉगिन के स्टोरी डाउनलोड नहीं हो सकती!\n\nकृपया पहले `/login` टाइप करके लॉगिन करें।")
        return
    await message.reply_text("👀 कृपया उस Instagram **यूजरनेम** या **प्रोफाइल लिंक** को भेजें जिसकी स्टोरीज डाउनलोड करनी हैं:")
    USER_STATE[chat_id] = {"step": "waiting_for_story_username"}

@app.on_message(filters.text & ~filters.command(["start", "posts", "reels", "highlight", "story", "login"]))
async def handle_text_inputs(client: Client, message: Message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = USER_STATE.get(chat_id, {})
    step = state.get("step")

    # 1. यूजरनेम लेना
    if step == "waiting_for_ig_username":
        USER_STATE[chat_id] = {"step": "waiting_for_ig_password", "ig_username": text}
        await message.reply_text(f"✅ Username मिला: `{text}`\n\n🔑 अब अपना Instagram **Password** भेजें:")
        return

    # 2. पासवर्ड चेक करना
    if step == "waiting_for_ig_password":
        username = state.get("ig_username")
        password = text
        status_msg = await message.reply_text("⏳ Instagram से कनेक्ट किया जा रहा है...")

        try:
            loop = asyncio.get_running_loop()
            success, msg = await loop.run_in_executor(
                None, interactive_instagram_login, username, password, None
            )

            if success is True:
                ACTIVE_LOGINS[chat_id] = {"username": username, "password": password}
                await status_msg.edit_text(f"🎉 **Login Successful!**\n✨ {msg}")
                USER_STATE.pop(chat_id, None)
            elif success == "2FA_REQUIRED":
                USER_STATE[chat_id] = {"step": "waiting_for_2fa", "ig_username": username, "ig_password": password}
                await status_msg.edit_text(msg)
            elif success == "CHALLENGE_REQUIRED":
                await status_msg.edit_text(msg)
                USER_STATE.pop(chat_id, None)
            else:
                await status_msg.edit_text(f"{msg}\n\n🔄 दोबारा कोशिश करने के लिए `/login` टाइप करें।")
                USER_STATE.pop(chat_id, None)
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** {str(e)}\n\n🔄 दोबारा कोशिश करने के लिए `/login` टाइप करें।")
            USER_STATE.pop(chat_id, None)
        return

    # 3. 2FA कोड चेक करना
    if step == "waiting_for_2fa":
        username = state.get("ig_username")
        password = state.get("ig_password")
        code = text
        status_msg = await message.reply_text("⏳ 2FA कोड वेरिफ़ाई हो रहा है...")

        try:
            loop = asyncio.get_running_loop()
            success, msg = await loop.run_in_executor(
                None, interactive_instagram_login, username, password, code
            )

            if success is True:
                ACTIVE_LOGINS[chat_id] = {"username": username, "password": password}
                await status_msg.edit_text(f"🎉 **2FA Verification Successful!**\n✨ {msg}")
                USER_STATE.pop(chat_id, None)
            else:
                await status_msg.edit_text(f"❌ **Wrong 2FA Code!**\n{msg}\n\n🔄 दोबारा लॉगिन करने के लिए फ़िर से `/login` टाइप करें।")
                USER_STATE.pop(chat_id, None)
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** {str(e)}\n\n🔄 दोबारा कोशिश करने के लिए `/login` टाइप करें।")
            USER_STATE.pop(chat_id, None)
        return

    # डायरेक्ट स्टोरी लिंक
    if "instagram.com/stories/" in text and "highlights" not in text:
        login_data = ACTIVE_LOGINS.get(chat_id)
        if not login_data:
            await message.reply_text("❌ बिना लॉगिन के स्टोरी डाउनलोड नहीं हो सकती! पहले `/login` करें।")
            return
        status_msg = await message.reply_text("⏳ स्टोरी डाउनलोड की जा रही है...")
        target_dir = None
        try:
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(
                None, download_story_by_link, text, login_data["username"], login_data["password"]
            )
            if files:
                for file in files:
                    if file.lower().endswith(('.mp4', '.mov')):
                        await message.reply_video(video=file, caption="✨ Story Downloaded via Bot")
                    else:
                        await message.reply_photo(photo=file, caption="✨ Story Downloaded via Bot")
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ इस स्टोरी से कोई मीडिया नहीं मिला।")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
        finally:
            if target_dir and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        return

    # डायरेक्ट हाइलाइट लिंक
    if "instagram.com/stories/highlights/" in text:
        login_data = ACTIVE_LOGINS.get(chat_id)
        if not login_data:
            await message.reply_text("❌ बिना लॉगिन के हाइलाइट डाउनलोड नहीं हो सकता! पहले `/login` करें।")
            return
        status_msg = await message.reply_text("⏳ हाइलाइट ZIP डाउनलोड की जा रही है...")
        zip_path = None
        try:
            loop = asyncio.get_running_loop()
            zip_path, count = await loop.run_in_executor(
                None, download_highlight_by_link, text, login_data["username"], login_data["password"]
            )
            if zip_path and os.path.exists(zip_path):
                await message.reply_document(document=zip_path, caption=f"✅ Highlight ZIP\n📦 Total: {count}")
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ हाइलाइट से कोई मीडिया नहीं मिला।")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
        finally:
            if zip_path and os.path.exists(zip_path):
                try: os.remove(zip_path)
                except: pass
        return

    # सिंगल पोस्ट/रील लिंक
    if "instagram.com/p/" in text or "instagram.com/reel/" in text:
        status_msg = await message.reply_text("⏳ मीडिया डाउनलोड किया जा रहा है...")
        target_dir = None
        try:
            parts = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")
            shortcode = parts[1] if len(parts) > 1 else parts[0]
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(None, download_single_link, shortcode)
            if files:
                for file in files:
                    if file.lower().endswith(('.mp4', '.mov')):
                        await message.reply_video(video=file)
                    else:
                        await message.reply_photo(photo=file)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ मीडिया नहीं मिला।")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
        finally:
            if target_dir and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        return

    if step == "waiting_for_username":
        login_data = ACTIVE_LOGINS.get(chat_id)
        username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
        status_msg = await message.reply_text(f"🔍 **@{username}** के हाइलाइट्स खोजे जा रहे हैं...")
        try:
            loop = asyncio.get_running_loop()
            highlights = await loop.run_in_executor(
                None, get_highlights_list, username, login_data["username"], login_data["password"]
            )
            if not highlights:
                await status_msg.edit_text("❌ कोई हाइलाइट नहीं मिला।")
                USER_STATE.pop(chat_id, None)
                return

            USER_STATE[chat_id] = {"username": username, "highlights": highlights, "downloaded": []}
            buttons = [[InlineKeyboardButton(f"📁 {h['title']}", callback_data=f"dl_hl_{username}_{h['title'][:20]}")] for h in highlights]
            await status_msg.edit_text(f"✅ कुल **{len(highlights)}** हाइलाइट्स मिले हैं। नीचे क्लिक करें:", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
            USER_STATE.pop(chat_id, None)
        return

    if step == "waiting_for_story_username":
        login_data = ACTIVE_LOGINS.get(chat_id)
        username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
        status_msg = await message.reply_text(f"🔍 **@{username}** की स्टोरीज खोजी जा रही हैं...")
        target_dir = None
        try:
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(
                None, download_user_stories, username, login_data["username"], login_data["password"]
            )
            if not files:
                await status_msg.edit_text("❌ कोई एक्टिव स्टोरी नहीं मिली।")
                USER_STATE.pop(chat_id, None)
                return

            for file in files:
                if file.lower().endswith(('.mp4', '.mov')):
                    await message.reply_video(video=file, caption=f"✨ @{username} Story")
                else:
                    await message.reply_photo(photo=file, caption=f"✨ @{username} Story")
            await status_msg.delete()
            USER_STATE.pop(chat_id, None)
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
            USER_STATE.pop(chat_id, None)
        finally:
            if target_dir and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        return

    username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
    if " " in username or len(username) > 30:
        await message.reply_text("❓ समझ नहीं आया। `/start` टाइप करें।")
        return

    login_data = ACTIVE_LOGINS.get(chat_id)
    ig_u = login_data["username"] if login_data else None
    ig_p = login_data["password"] if login_data else None

    status_msg = await message.reply_text(f"🔍 **@{username}** की प्रोफाइल चेक की जा रही है...")
    try:
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, get_profile_stats, username, ig_u, ig_p)
        if stats:
            info_text = (
                f"📊 **Instagram Profile Info**\n\n"
                f"👤 **Username:** `@{stats['username']}`\n"
                f"📦 **Total Posts:** `{stats['total_posts']}`\n"
                f"🔒 **Account Type:** `{'Private ❌' if stats['is_private'] else 'Public ✅'}`\n\n"
                f"💡 **डाउनलोड कमांड:**\n"
                f"• `/posts {stats['username']} 1 100`\n"
                f"• `/reels {stats['username']} 1 50`"
            )
            await status_msg.edit_text(info_text)
        else:
            await status_msg.edit_text("❌ प्रोफाइल जानकारी नहीं मिली।")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

@app.on_callback_query(filters.regex("^dl_hl_"))
async def handle_highlight_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    login_data = ACTIVE_LOGINS.get(chat_id)
    if not login_data:
        await callback_query.answer("लॉगिन समाप्त हो गया है, कृपया फिर से लॉगिन करें!", show_alert=True)
        return

    parts = data.replace("dl_hl_", "").split("_", 1)
    username = parts[0]
    hl_title = parts[1] if len(parts) > 1 else ""

    await callback_query.answer(f"⏳ '{hl_title}' डाउनलोड हो रहा है...")
    status_msg = await callback_query.message.reply_text(f"⏳ हाइलाइट **'{hl_title}'** डाउनलोड हो रहा है...")

    zip_path = None
    try:
        loop = asyncio.get_running_loop()
        zip_path, count = await loop.run_in_executor(
            None, download_specific_highlight, username, hl_title, login_data["username"], login_data["password"]
        )
        if zip_path and os.path.exists(zip_path):
            await callback_query.message.reply_document(document=zip_path, caption=f"✅ Highlight: `{hl_title}`\n📦 Count: {count}")
            await status_msg.delete()

            if chat_id in USER_STATE:
                if "downloaded" not in USER_STATE[chat_id]: USER_STATE[chat_id]["downloaded"] = []
                USER_STATE[chat_id]["downloaded"].append(hl_title)
                
                remaining = [h for h in USER_STATE[chat_id]["highlights"] if h['title'] not in USER_STATE[chat_id]["downloaded"]]
                if remaining:
                    buttons = [[InlineKeyboardButton(f"📁 {h['title']}", callback_data=f"dl_hl_{username}_{h['title'][:20]}")] for h in remaining]
                    await callback_query.message.reply_text("👇 **बाकी बचे हाइलाइट्स:**", reply_markup=InlineKeyboardMarkup(buttons))
                else:
                    await callback_query.message.reply_text("🎉 सभी हाइलाइट्स डाउनलोड हो चुके हैं!")
                    USER_STATE.pop(chat_id, None)
        else:
            await status_msg.edit_text("❌ इस हाइलाइट में कोई मीडिया नहीं मिला।")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if zip_path and os.path.exists(zip_path):
            try: os.remove(zip_path)
            except: pass

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("🤖 Bot & Web Server are running together...")
    app.run()
        
