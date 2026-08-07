import os

# Render Environment Variables से वैल्यू लेना (यदि उपलब्ध न हो तो डिफ़ॉल्ट मान)
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Admin User IDs को Render से कॉमा (,) से अलग करके लिस्ट के रूप में पढ़ना
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(",") if i.strip().isdigit()]

# Force Channels को भी Render से पढ़ना (कॉमा से अलग करके)
force_channels_str = os.environ.get("FORCE_CHANNELS", "")
FORCE_CHANNELS = [ch.strip() for ch in force_channels_str.split(",") if ch.strip()]

SHORTENER_API = os.environ.get("SHORTENER_API", "")
SHORTENER_URL = os.environ.get("SHORTENER_URL", "")
VERIFY_EXPIRE_HOURS = int(os.environ.get("VERIFY_EXPIRE_HOURS", "24"))
