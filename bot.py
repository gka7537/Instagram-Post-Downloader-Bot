import os
import time
import shutil
import asyncio
import threading
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import API_ID, API_HASH, BOT_TOKEN, SHORTENER_API, SHORTENER_URL, VERIFY_EXPIRE_HOURS, FORCE_CHANNELS, ADMIN_IDS
from downloader import (
    get_highlights_list, download_specific_highlight, download_single_link, 
    download_highlight_by_link, download_user_stories, download_story_by_link, 
    get_profile_stats, download_specific_content, interactive_instagram_login
)

ACTIVE_LOGINS = {}
USER_VERIFY = {}  # {chat_id: expiry_timestamp}
MAX_DOWNLOAD_LIMIT = 50

app = Client("insta_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
USER_STATE = {}

server = Flask(__name__)
@server.route('/')
def home():
    return "🤖 Instagram Downloader Bot is Active and Running! / बोट एक्टिव और चालू है!"

def run_flask():
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 1000)))

def get_shortened_link(original_url):
    if not SHORTENER_API or not SHORTENER_URL:
        return original_url
    try:
        api_endpoint = f"https://{SHORTENER_URL}/api?api={SHORTENER_API}&url={original_url}"
        response = requests.get(api_endpoint).json()
        if response.get("status") == "success":
            return response.get("shortenedUrl")
    except:
        pass
    return original_url

async def check_force_sub(client: Client, user_id: int):
    if user_id in ADMIN_IDS:
        return []
        
    if not FORCE_CHANNELS:
        return []
    
    not_joined = []
    for channel in FORCE_CHANNELS:
        try:
            member = await client.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
            
    return not_joined

def get_join_markup_and_message():
    buttons = [[InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.replace('@', '')}")] for ch in FORCE_CHANNELS]
    buttons.append([InlineKeyboardButton("🔄 Try Again / दोबारा कोशिश करें", callback_data="check_sub")])
    
    text = (
        "⚠️ **पहले चैनल जॉइन करें! / Please join the channel first!**\n\n"
        "बोट का उपयोग करने के लिए नीचे दिए गए सभी चैनलों को जॉइन करें:\n"
        "Please join all the channels given below to use the bot:\n\n"
        "💡 *Note: अगर आप पहले से जॉइन हैं, तो कृपया चैनल को Leave करके दोबारा Join करें!*\n"
        "💡 *Note: If you have already joined, please leave and join the channel again!*"
    )
    return text, InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if len(message.command) > 1 and message.command[1] == "verify":
        USER_VERIFY[chat_id] = time.time() + (VERIFY_EXPIRE_HOURS * 3600)
        await message.reply_text(f"🎉 **Verification Successful! / वेरीफिकेशन सफल रहा!**\n\nअब आप अगले {VERIFY_EXPIRE_HOURS} घंटे तक सभी Files और Albums डाउनलोड कर सकते हैं।\nNow you can download all files & albums for the next {VERIFY_EXPIRE_HOURS} hours.")
        return

    missing_channels = await check_force_sub(client, user_id)
    if missing_channels:
        msg_text, markup = get_join_markup_and_message()
        await message.reply_text(msg_text, reply_markup=markup)
        return

    if user_id not in ADMIN_IDS and SHORTENER_API and SHORTENER_URL:
        current_time = time.time()
        expire_time = USER_VERIFY.get(chat_id, 0)
        
        if current_time > expire_time:
            bot_info = await client.get_me()
            verify_target_url = f"https://t.me/{bot_info.username}?start=verify"
            short_link = get_shortened_link(verify_target_url)
            
            verify_btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Click Here to Verify / यहाँ क्लिक करें", url=short_link)],
                [InlineKeyboardButton("❓ How to Verify? / वेरीफाई कैसे करें?", callback_data="how_to_verify")]
            ])
            await message.reply_text(
                f"⚠️ **Verify once to get unlimited File & Album access for the next {VERIFY_EXPIRE_HOURS} hours!**\n\n"
                f"असीमित एक्सेस पाने के लिए एक बार वेरिफाई करें (अगले {VERIFY_EXPIRE_HOURS} घंटे के लिए)।",
                reply_markup=verify_btn
            )
            return

    help_text = (
        "🤖 **Instagram Advanced Downloader Bot**\n\n"
        "✨ **इस्तेमाल करने का तरीका / How to use:**\n"
        "1. `/login` - अकाउंट लॉगिन करें / Login your account (Permanent Session)\n"
        "2. किसी भी यूजर का **यूजरनेम या लिंक** भेजें $\rightarrow$ कुल पोस्ट्स दिखेंगे / Send username or link.\n"
        "3. रेंज भेजें (जैसे: `1 20`) $\rightarrow$ ZIP फाइल मिल जाएगी / Send range for ZIP.\n"
        "4. `/story` या `/highlight` का उपयोग करें / Use /story or /highlight."
    )
    await message.reply_text(help_text)

@app.on_callback_query(filters.regex("how_to_verify"))
async def how_to_verify_callback(client: Client, callback_query: CallbackQuery):
    help_msg = (
        "📖 **वेरीफाई करने का तरीका (How to Verify):**\n\n"
        "1. सबसे पहले 'Click Here to Verify' बटन पर क्लिक करें / Click the verify button.\n"
        "2. वेबसाइट खुलने पर नीचे जाएं और 'Open / Continue' या 'Verify' बटन दबाएं / Click continue/verify.\n"
        "3. कुछ सेकंड प्रतीक्षा करें, लिंक जनरेट होने के बाद ऑटोमैटिकली बोट पर वापस आ जाएंगे!"
    )
    await callback_query.answer(help_msg, show_alert=True)

@app.on_callback_query(filters.regex("check_sub"))
async def sub_callback(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    missing_channels = await check_force_sub(client, user_id)
    if missing_channels:
        await callback_query.answer("❌ आपने अभी तक सभी चैनल जॉइन नहीं किए हैं!\nYou haven't joined all channels yet!", show_alert=True)
    else:
        await callback_query.message.delete()
        await callback_query.message.reply_text("✅ धन्यवाद! अब अपना काम जारी रखने के लिए `/start` टाइप करें।\n✅ Thank you! Type `/start` to continue.")

@app.on_message(filters.command("login"))
async def login_command(client: Client, message: Message):
    chat_id = message.chat.id
    await message.reply_text("👤 कृपया अपना Instagram **Username** भेजें:\nPlease send your Instagram **Username**:")
    USER_STATE[chat_id] = {"step": "waiting_for_ig_username"}

@app.on_message(filters.command("highlight"))
async def highlight_command(client: Client, message: Message):
    chat_id = message.chat.id
    login_data = ACTIVE_LOGINS.get(chat_id)
    if not login_data:
        await message.reply_text("❌ बिना लॉगिन के हाइलाइट डाउनलोड नहीं हो सकता! पहले `/login` करें。\n❌ Login required to download highlights! Please `/login` first.")
        return
    await message.reply_text("📂 कृपया उस Instagram **यूजरनेम** या **प्रोफाइल लिंक** को भेजें जिसके हाइलाइट्स देखने हैं:\nPlease send username/link to view highlights:")
    USER_STATE[chat_id] = {"step": "waiting_for_username"}

@app.on_message(filters.command("story"))
async def story_command(client: Client, message: Message):
    chat_id = message.chat.id
    login_data = ACTIVE_LOGINS.get(chat_id)
    if not login_data:
        await message.reply_text("❌ बिना लॉगिन के स्टोरी डाउनलोड नहीं हो सकती! पहले `/login` करें。\n❌ Login required to download stories! Please `/login` first.")
        return
    await message.reply_text("👀 कृपया उस Instagram **यूजरनेम** या **प्रोफाइल लिंक** को भेजें जिसकी स्टोरीज डाउनलोड करनी हैं:\nPlease send username/link to download stories:")
    USER_STATE[chat_id] = {"step": "waiting_for_story_username"}

@app.on_message(filters.text & ~filters.command(["start", "highlight", "story", "login"]))
async def handle_text_inputs(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()
    
    missing_channels = await check_force_sub(client, user_id)
    if missing_channels:
        msg_text, markup = get_join_markup_and_message()
        await message.reply_text(msg_text, reply_markup=markup)
        return

    if user_id not in ADMIN_IDS and SHORTENER_API and SHORTENER_URL:
        if time.time() > USER_VERIFY.get(chat_id, 0):
            await message.reply_text("⚠️ कृपया पहले `/start` भेजकर वेरीफाई करें!\nPlease verify by sending `/start` first!")
            return

    state = USER_STATE.get(chat_id, {})
    step = state.get("step")

    if step == "waiting_for_ig_username":
        USER_STATE[chat_id] = {"step": "waiting_for_ig_password", "ig_username": text}
        await message.reply_text(f"✅ Username मिला / Received: `{text}`\n\n🔑 अब अपना Instagram **Password** भेजें:\nNow send your Instagram **Password**:")
        return

    if step == "waiting_for_ig_password":
        username = state.get("ig_username")
        password = text
        status_msg = await message.reply_text("⏳ Instagram से कनेक्ट किया जा रहा है...\n⏳ Connecting to Instagram...")

        try:
            loop = asyncio.get_running_loop()
            success, msg = await loop.run_in_executor(None, interactive_instagram_login, username, password, None)

            if success is True:
                ACTIVE_LOGINS[chat_id] = {"username": username, "password": password}
                await status_msg.edit_text(f"🎉 **Login Successful & Saved Permanently!**\n🎉 **लॉगिन सफल और परमानेंट सुरक्षित हो गया है!**\n✨ {msg}")
                USER_STATE.pop(chat_id, None)
            elif success == "2FA_REQUIRED":
                USER_STATE[chat_id] = {"step": "waiting_for_2fa", "ig_username": username, "ig_password": password}
                await status_msg.edit_text(msg)
            elif success == "CHALLENGE_REQUIRED":
                await status_msg.edit_text(msg)
                USER_STATE.pop(chat_id, None)
            else:
                await status_msg.edit_text(f"{msg}\n\n🔄 `/login` से दोबारा प्रयास करें / Try again with `/login`.")
                USER_STATE.pop(chat_id, None)
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error / त्रुटि:** {str(e)}")
            USER_STATE.pop(chat_id, None)
        return

    if step == "waiting_for_2fa":
        username = state.get("ig_username")
        password = state.get("ig_password")
        code = text
        status_msg = await message.reply_text("⏳ 2FA कोड वेरिफ़ाई हो रहा है...\n⏳ Verifying 2FA code...")

        try:
            loop = asyncio.get_running_loop()
            success, msg = await loop.run_in_executor(None, interactive_instagram_login, username, password, code)

            if success is True:
                ACTIVE_LOGINS[chat_id] = {"username": username, "password": password}
                await status_msg.edit_text(f"🎉 **2FA Success & Permanent Session Saved!**\n🎉 **2FA सफल और सेशन सुरक्षित हो गया है!**\n✨ {msg}")
                USER_STATE.pop(chat_id, None)
            else:
                await status_msg.edit_text(f"❌ **Wrong 2FA Code! / गलत 2FA कोड!**\n{msg}")
                USER_STATE.pop(chat_id, None)
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error / त्रुटि:** {str(e)}")
            USER_STATE.pop(chat_id, None)
        return

    if step == "waiting_for_range":
        target_username = state.get("target_username")
        try:
            parts = text.replace(",", " ").split()
            if len(parts) != 2: raise ValueError
            start_idx, end_idx = int(parts[0]), int(parts[1])
        except ValueError:
            await message.reply_text("❌ गलत फॉर्मेट! केवल दो नंबर दें (जैसे: `1 20`):\n❌ Invalid format! Provide two numbers (e.g., `1 20`):")
            return

        if (end_idx - start_idx + 1) > MAX_DOWNLOAD_LIMIT:
            await message.reply_text(f"⚠️ अधिकतम लिमिट **{MAX_DOWNLOAD_LIMIT}** पोस्ट की है!\n⚠️ Max limit is **{MAX_DOWNLOAD_LIMIT}** posts!")
            return

        USER_STATE.pop(chat_id, None)
        login_data = ACTIVE_LOGINS.get(chat_id)
        ig_u = login_data["username"] if login_data else None
        ig_p = login_data["password"] if login_data else None

        status_msg = await message.reply_text(f"⏳ **@{target_username}** के पोस्ट्स डाउनलोड हो रहे हैं...\n⏳ Downloading posts for @{target_username}...")
        zip_path = None
        try:
            loop = asyncio.get_running_loop()
            zip_path, count = await loop.run_in_executor(None, download_specific_content, target_username, start_idx, end_idx, ig_u, ig_p)

            if zip_path and os.path.exists(zip_path):
                await status_msg.edit_text("📤 ZIP फाइल भेजी जा रही है...\n📤 Sending ZIP file...")
                await message.reply_document(document=zip_path, caption=f"✅ **@{target_username}** Posts ({start_idx}-{end_idx})\n📦 Total / कुल: {count}")
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ इस रेंज में कोई पोस्ट नहीं मिला。\n❌ No posts found in this range.")
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error / त्रुटि:** `{str(e)}`")
        finally:
            if zip_path and os.path.exists(zip_path):
                try: os.remove(zip_path)
                except: pass
        return

    if "instagram.com/stories/" in text and "highlights" not in text:
        login_data = ACTIVE_LOGINS.get(chat_id)
        if not login_data:
            await message.reply_text("❌ बिना लॉगिन के स्टोरी डाउनलोड नहीं हो सकती! पहले `/login` करें。\n❌ Login required to download stories! Please `/login` first.")
            return
        status_msg = await message.reply_text("⏳ स्टोरी डाउनलोड की जा रही है...\n⏳ Downloading story...")
        target_dir = None
        try:
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(
                None, download_story_by_link, text, login_data["username"], login_data["password"]
            )
            if files:
                for file in files:
                    if file.lower().endswith(('.mp4', '.mov')):
                        await message.reply_video(video=file, caption="✨ Story Downloaded via Bot / बोट द्वारा डाउनलोड की गई स्टोरी")
                    else:
                        await message.reply_photo(photo=file, caption="✨ Story Downloaded via Bot / बोट द्वारा डाउनलोड की गई स्टोरी")
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ इस स्टोरी से कोई मीडिया नहीं मिला。\n❌ No media found in this story.")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")
        finally:
            if target_dir and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        return

    if "instagram.com/stories/highlights/" in text:
        login_data = ACTIVE_LOGINS.get(chat_id)
        if not login_data:
            await message.reply_text("❌ बिना लॉगिन के हाइलाइट डाउनलोड नहीं हो सकता! पहले `/login` करें。\n❌ Login required to download highlights! Please `/login` first.")
            return
        status_msg = await message.reply_text("⏳ हाइलाइट ZIP डाउनलोड की जा रही है...\n⏳ Downloading highlight ZIP...")
        zip_path = None
        try:
            loop = asyncio.get_running_loop()
            zip_path, count = await loop.run_in_executor(
                None, download_highlight_by_link, text, login_data["username"], login_data["password"]
            )
            if zip_path and os.path.exists(zip_path):
                await message.reply_document(document=zip_path, caption=f"✅ Highlight ZIP\n📦 Total / कुल: {count}")
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ हाइलाइट से कोई मीडिया नहीं मिला。\n❌ No media found in highlight.")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")
        finally:
            if zip_path and os.path.exists(zip_path):
                try: os.remove(zip_path)
                except: pass
        return

    if "instagram.com/p/" in text or "instagram.com/reel/" in text:
        status_msg = await message.reply_text("⏳ मीडिया डाउनलोड किया जा रहा है...\n⏳ Downloading media...")
        target_dir = None
        try:
            login_data = ACTIVE_LOGINS.get(chat_id)
            ig_u = login_data["username"] if login_data else None
            ig_p = login_data["password"] if login_data else None

            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(None, download_single_link, text, ig_u, ig_p)
            if files:
                for file in files:
                    if file.lower().endswith(('.mp4', '.mov', '.webm')):
                        await message.reply_video(video=file)
                    else:
                        await message.reply_photo(photo=file)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ मीडिया नहीं मिला。\n❌ Media not found.")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")
        finally:
            if target_dir and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        return

    if step == "waiting_for_username":
        login_data = ACTIVE_LOGINS.get(chat_id)
        username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
        status_msg = await message.reply_text(f"🔍 **@{username}** के हाइलाइट्स खोजे जा रहे हैं...\n🔍 Searching highlights for @{username}...")
        try:
            loop = asyncio.get_running_loop()
            highlights = await loop.run_in_executor(
                None, get_highlights_list, username, login_data["username"], login_data["password"]
            )
            if not highlights:
                await status_msg.edit_text("❌ कोई हाइलाइट नहीं मिला。\n❌ No highlights found.")
                USER_STATE.pop(chat_id, None)
                return

            USER_STATE[chat_id] = {"username": username, "highlights": highlights, "downloaded": []}
            buttons = [[InlineKeyboardButton(f"📁 {h['title']}", callback_data=f"dl_hl_{username}_{h['title'][:20]}")] for h in highlights]
            await status_msg.edit_text(f"✅ कुल **{len(highlights)}** हाइलाइट्स मिले हैं। नीचे क्लिक करें:\n✅ Total **{len(highlights)}** highlights found. Click below:", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")
            USER_STATE.pop(chat_id, None)
        return

    if step == "waiting_for_story_username":
        login_data = ACTIVE_LOGINS.get(chat_id)
        username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
        status_msg = await message.reply_text(f"🔍 **@{username}** की स्टोरीज खोजी जा रही हैं...\n🔍 Searching stories for @{username}...")
        target_dir = None
        try:
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(
                None, download_user_stories, username, login_data["username"], login_data["password"]
            )
            if not files:
                await status_msg.edit_text("❌ कोई एक्टिव स्टोरी नहीं मिली。\n❌ No active story found.")
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
            await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")
            USER_STATE.pop(chat_id, None)
        finally:
            if target_dir and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        return

    username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
    if " " in username or len(username) > 30:
        await message.reply_text("❓ समझ नहीं आया। `/start` टाइप करें。\n❓ Didn't understand. Type `/start`.")
        return

    login_data = ACTIVE_LOGINS.get(chat_id)
    ig_u = login_data["username"] if login_data else None
    ig_p = login_data["password"] if login_data else None

    status_msg = await message.reply_text(f"🔍 **@{username}** की प्रोफाइल चेक की जा रही है...\n🔍 Checking profile for @{username}...")
    try:
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, get_profile_stats, username, ig_u, ig_p)
        if stats:
            USER_STATE[chat_id] = {"step": "waiting_for_range", "target_username": stats['username']}
            info_text = (
                f"📊 **Instagram Profile Info / प्रोफाइल जानकारी**\n\n"
                f"👤 **Username:** `@{stats['username']}`\n"
                f"📦 **Total Posts / कुल पोस्ट:** `{stats['total_posts']}`\n"
                f"🔒 **Account Type:** `{'Private ❌' if stats['is_private'] else 'Public ✅'}`\n\n"
                f"⚡ **डाउनलोड लिमिट / Download Limit:** अधिकतम **{MAX_DOWNLOAD_LIMIT}** पोस्ट्स प्रति बार / Max {MAX_DOWNLOAD_LIMIT} posts per batch.\n\n"
                f"📥 **अब रेंज भेजें (जैसे: `1 20`):\nNow send range (e.g., `1 20`):**"
            )
            await status_msg.edit_text(info_text)
        else:
            await status_msg.edit_text("❌ प्रोफाइल जानकारी नहीं मिली。\n❌ Profile info not found.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")

@app.on_callback_query(filters.regex("^dl_hl_"))
async def handle_highlight_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    login_data = ACTIVE_LOGINS.get(chat_id)
    if not login_data:
        await callback_query.answer("लॉगिन समाप्त हो गया है, कृपया फिर से लॉगिन करें!\nLogin expired, please login again!", show_alert=True)
        return

    parts = data.replace("dl_hl_", "").split("_", 1)
    username = parts[0]
    hl_title = parts[1] if len(parts) > 1 else ""

    await callback_query.answer(f"⏳ '{hl_title}' डाउनलोड हो रहा है...")
    status_msg = await callback_query.message.reply_text(f"⏳ हाइलाइट **'{hl_title}'** डाउनलोड हो रहा है...\n⏳ Downloading highlight '{hl_title}'...")

    zip_path = None
    try:
        loop = asyncio.get_running_loop()
        zip_path, count = await loop.run_in_executor(
            None, download_specific_highlight, username, hl_title, login_data["username"], login_data["password"]
        )
        if zip_path and os.path.exists(zip_path):
            await callback_query.message.reply_document(document=zip_path, caption=f"✅ Highlight: `{hl_title}`\n📦 Count / कुल: {count}")
            await status_msg.delete()

            if chat_id in USER_STATE:
                if "downloaded" not in USER_STATE[chat_id]: USER_STATE[chat_id]["downloaded"] = []
                USER_STATE[chat_id]["downloaded"].append(hl_title)
                
                remaining = [h for h in USER_STATE[chat_id]["highlights"] if h['title'] not in USER_STATE[chat_id]["downloaded"]]
                if remaining:
                    buttons = [[InlineKeyboardButton(f"📁 {h['title']}", callback_data=f"dl_hl_{username}_{h['title'][:20]}")] for h in remaining]
                    await callback_query.message.reply_text("👇 **बाकी बचे हाइलाइट्स / Remaining Highlights:**", reply_markup=InlineKeyboardMarkup(buttons))
                else:
                    await callback_query.message.reply_text("🎉 सभी हाइलाइट्स डाउनलोड हो चुके हैं!\n🎉 All highlights downloaded successfully!")
                    USER_STATE.pop(chat_id, None)
        else:
            await status_msg.edit_text("❌ इस हाइलाइट में कोई मीडिया नहीं मिला。\n❌ No media found in this highlight.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error / त्रुटि: {str(e)}")
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
    
