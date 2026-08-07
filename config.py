import os

# API Credentials
try:
    API_ID = int(os.environ.get("API_ID", "0") or "0")
except ValueError:
    API_ID = 0

API_HASH = os.environ.get("API_HASH", False)
BOT_TOKEN = os.environ.get("BOT_TOKEN", False)

# Admin User IDs
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(",") if i.strip().isdigit()]

# Force Channels
force_channels_str = os.environ.get("FORCE_CHANNELS", "")
FORCE_CHANNELS = [ch.strip() for ch in force_channels_str.split(",") if ch.strip()]

# Shortener Settings (अगर खाली हों तो इन्हें False माना जाएगा)
SHORTENER_API = os.environ.get("SHORTENER_API", False) or False
SHORTENER_URL = os.environ.get("SHORTENER_URL", False) or False

# Verification Expiry Time
try:
    VERIFY_EXPIRE_HOURS = int(os.environ.get("VERIFY_EXPIRE_HOURS", "24") or "24")
except ValueError:
    VERIFY_EXPIRE_HOURS = 24
  
