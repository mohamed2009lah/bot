import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

API_KEY = os.getenv("SHRINKEARN_API_KEY", "")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN missing")
