import os

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# शॉर्टनर और वेरीफिकेशन सेटिंग्स (Render से कंट्रोल होंगी)
SHORTENER_API = os.getenv("SHORTENER_API", "")
SHORTENER_URL = os.getenv("SHORTENER_URL", "")
VERIFY_EXPIRE_HOURS = int(os.getenv("VERIFY_EXPIRE_HOURS", 24))

# मल्टीपल फोर्स सब्सक्रिप्शन चैनल (जैसे: @chan1,@chan2)
CHANNELS_ENV = os.getenv("FORCE_CHANNELS", "")
FORCE_CHANNELS = [ch.strip() for ch in CHANNELS_ENV.split(",") if ch.strip()]

