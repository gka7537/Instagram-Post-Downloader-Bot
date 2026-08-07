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
    get_profile_stats, download_specific_content
)

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

# Pyrogram Bot Client
app = Client(
    "insta_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

USER_STATE = {}

# --- Flask Web Server (Port 1000) ---
server = Flask(__name__)

@server.route('/')
def home():
    return "🤖 Instagram Downloader Bot is Active and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 1000))
    server.run(host="0.0.0.0", port=port)
# -------------------------------------------------------------

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    help_text = (
        "🤖 **Instagram Advanced Downloader Bot**\n\n"
        "✨ **सुविधाएँ:**\n"
        "• **Profile Info:** कोई भी यूजरनेम या लिंक भेजें, कुल पोस्ट्स तुरंत दिखेंगे।\n"
        "• **Posts/Reels:** `/posts username start end` या `/reels username start end`\n"
        "• **Story:** `/story` टाइप करके यूजरनेम दें या सीधे स्टोरी का लिंक भेजें।\n"
        "• **Highlight:** `/highlight` टाइप करें या हाइलाइट का सीधा लिंक भेजें।\n"
        "• **Single Media:** किसी भी पोस्ट/रील का सीधा लिंक भेजें।"
    )
    await message.reply_text(help_text)

# 1. /posts कमांड
@app.on_message(filters.command("posts"))
async def handle_posts_command(client: Client, message: Message):
    args = message.command
    if len(args) < 2:
        await message.reply_text("❌ सही तरीका:\n`/posts username start end`\nउदाहरण: `/posts instagram 1 100`")
        return
    
    username = args[1].replace("@", "").strip()
    try:
        start_idx = int(args[2]) if len(args) > 2 else 1
        end_idx = int(args[3]) if len(args) > 3 else 100
    except ValueError:
        await message.reply_text("❌ कृपया सही नंबर लिखें।")
        return

    status_msg = await message.reply_text(f"⏳ **@{username}** के पोस्ट्स ({start_idx} से {end_idx}) डाउनलोड हो रहे हैं...")
    zip_path = None
    try:
        loop = asyncio.get_running_loop()
        zip_path, count = await loop.run_in_executor(
            None, download_specific_content, username, 'posts', start_idx, end_idx, IG_USERNAME, IG_PASSWORD
        )

        if zip_path and os.path.exists(zip_path):
            await status_msg.edit_text(f"📤 कुल {count} पोस्ट्स की ZIP फाइल भेजी जा रही है...")
            await message.reply_document(document=zip_path, caption=f"✅ **@{username}** Posts ({start_idx} - {end_idx})\n📦 Count: {count}")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ इस रेंज में कोई पोस्ट नहीं मिला।")
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
    finally:
        if zip_path and os.path.exists(zip_path):
            try: os.remove(zip_path)
            except: pass

# 2. /reels कमांड
@app.on_message(filters.command("reels"))
async def handle_reels_command(client: Client, message: Message):
    args = message.command
    if len(args) < 2:
        await message.reply_text("❌ सही तरीका:\n`/reels username start end`\nउदाहरण: `/reels instagram 1 50`")
        return
    
    username = args[1].replace("@", "").strip()
    try:
        start_idx = int(args[2]) if len(args) > 2 else 1
        end_idx = int(args[3]) if len(args) > 3 else 50
    except ValueError:
        await message.reply_text("❌ कृपया सही नंबर लिखें।")
        return

    status_msg = await message.reply_text(f"⏳ **@{username}** की रील्स डाउनलोड हो रही हैं...")
    zip_path = None
    try:
        loop = asyncio.get_running_loop()
        zip_path, count = await loop.run_in_executor(
            None, download_specific_content, username, 'reels', start_idx, end_idx, IG_USERNAME, IG_PASSWORD
        )

        if zip_path and os.path.exists(zip_path):
            await status_msg.edit_text(f"📤 कुल {count} रील्स की ZIP फाइल भेजी जा रही है...")
            await message.reply_document(document=zip_path, caption=f"✅ **@{username}** Reels ({start_idx} - {end_idx})\n📦 Count: {count}")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ इस रेंज में कोई रील नहीं मिली।")
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
    finally:
        if zip_path and os.path.exists(zip_path):
            try: os.remove(zip_path)
            except: pass

# 3. /highlight कमांड
@app.on_message(filters.command("highlight"))
async def highlight_command(client: Client, message: Message):
    chat_id = message.chat.id
    await message.reply_text("📂 कृपया उस Instagram **यूजरनेम** या **प्रोफाइल लिंक** को भेजें जिसके हाइलाइट्स देखने हैं:")
    USER_STATE[chat_id] = {"step": "waiting_for_username"}

# 4. /story कमांड
@app.on_message(filters.command("story"))
async def story_command(client: Client, message: Message):
    chat_id = message.chat.id
    await message.reply_text("👀 कृपया उस Instagram **यूजरनेम** या **प्रोफाइल लिंक** को भेजें जिसकी स्टोरीज डाउनलोड करनी हैं:")
    USER_STATE[chat_id] = {"step": "waiting_for_story_username"}

# टेक्स्ट और लिंक हैंडलर
@app.on_message(filters.text & ~filters.command(["start", "posts", "reels", "highlight", "story"]))
async def handle_text_inputs(client: Client, message: Message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # डायरेक्ट स्टोरी लिंक
    if "instagram.com/stories/" in text and "highlights" not in text:
        status_msg = await message.reply_text("⏳ स्टोरी डाउनलोड की जा रही है...")
        target_dir = None
        try:
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(None, download_story_by_link, text, IG_USERNAME, IG_PASSWORD)
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
        status_msg = await message.reply_text("⏳ हाइलाइट ZIP डाउनलोड की जा रही है...")
        zip_path = None
        try:
            loop = asyncio.get_running_loop()
            zip_path, count = await loop.run_in_executor(None, download_highlight_by_link, text, IG_USERNAME, IG_PASSWORD)
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

    # /highlight स्टेट हैंडलर
    if USER_STATE.get(chat_id, {}).get("step") == "waiting_for_username":
        username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
        status_msg = await message.reply_text(f"🔍 **@{username}** के हाइलाइट्स खोजे जा रहे हैं...")
        try:
            loop = asyncio.get_running_loop()
            highlights = await loop.run_in_executor(None, get_highlights_list, username, IG_USERNAME, IG_PASSWORD)
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

    # /story स्टेट हैंडलर
    if USER_STATE.get(chat_id, {}).get("step") == "waiting_for_story_username":
        username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
        status_msg = await message.reply_text(f"🔍 **@{username}** की स्टोरीज खोजी जा रही हैं...")
        target_dir = None
        try:
            loop = asyncio.get_running_loop()
            files, target_dir = await loop.run_in_executor(None, download_user_stories, username, IG_USERNAME, IG_PASSWORD)
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

    # साधारण यूजरनेम भेजने पर प्रोफाइल स्टेट्स दिखाना
    username = text.split("instagram.com/")[1].split("?")[0].strip("/").split("/")[0] if "instagram.com/" in text else text.replace("@", "").strip()
    if " " in username or len(username) > 30:
        await message.reply_text("❓ समझ नहीं आया। `/start` टाइप करें।")
        return

    status_msg = await message.reply_text(f"🔍 **@{username}** की प्रोफाइल चेक की जा रही है...")
    try:
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, get_profile_stats, username, IG_USERNAME, IG_PASSWORD)
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

# हाइलाइट बटन क्लिक हैंडलर
@app.on_callback_query(filters.regex("^dl_hl_"))
async def handle_highlight_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    parts = data.replace("dl_hl_", "").split("_", 1)
    username = parts[0]
    hl_title = parts[1] if len(parts) > 1 else ""

    await callback_query.answer(f"⏳ '{hl_title}' डाउनलोड हो रहा है...")
    status_msg = await callback_query.message.reply_text(f"⏳ हाइलाइट **'{hl_title}'** डाउनलोड हो रहा है...")

    zip_path = None
    try:
        loop = asyncio.get_running_loop()
        zip_path, count = await loop.run_in_executor(None, download_specific_highlight, username, hl_title, IG_USERNAME, IG_PASSWORD)
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
                
