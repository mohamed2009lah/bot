import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

API_KEY = os.getenv("SHRINKEARN_API_KEY", "")

# ========== إعدادات النقاط ==========
REFERRAL_POINTS = int(os.getenv("REFERRAL_POINTS", "5"))  # نقاط لكل دعوة
DAILY_BONUS_POINTS = int(os.getenv("DAILY_BONUS_POINTS", "2"))  # نقاط يومية
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "2.0"))  # الحد الأدنى للسحب

# ========== إعدادات الإعلانات ==========
SHOW_ADS_BEFORE_SERVICES = os.getenv("SHOW_ADS_BEFORE_SERVICES", "true").lower() == "true"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN missing")
