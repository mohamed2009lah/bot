import os
import re
import json
import sqlite3
import random
import string
import asyncio
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SHRINKEARN_API_KEY = os.getenv("SHRINKEARN_API_KEY")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

DB_PATH = "bot_data.db"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# مراحل المحادثة
WAITING_FOR_LINK, WAITING_FOR_BINANCE_ID = range(2)

# ========== قاعدة البيانات ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0.0,
        total_earned REAL DEFAULT 0.0,
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        original_url TEXT,
        short_url TEXT,
        total_views INTEGER DEFAULT 0,
        total_earned REAL DEFAULT 0.0,
        last_earned REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        binance_id TEXT,
        status TEXT DEFAULT 'pending',
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_PATH)

def generate_referral_code(user_id):
    return f"REF{user_id}{random.randint(100,999)}"

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

async def shorten_link_api(original_url):
    api_url = "https://shrinkearn.com/api"
    params = {"api": SHRINKEARN_API_KEY, "url": original_url, "format": "json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, params=params, timeout=10) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return data["shortenedUrl"]
                return None
        except Exception as e:
            logger.error(f"Shorten error: {e}")
            return None

async def get_link_stats(short_url):
    api_url = "https://shrinkearn.com/api"
    params = {"api": SHRINKEARN_API_KEY, "url": short_url, "format": "json", "action": "stats"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, params=params, timeout=10) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    return {"views": int(data.get("views", 0)), "earned": float(data.get("earned", 0))}
                return None
        except:
            return None

# ========== وظائف المستخدمين ==========
def register_user(user_id, username, referred_by=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        code = generate_referral_code(user_id)
        while c.execute("SELECT user_id FROM users WHERE referral_code=?", (code,)).fetchone():
            code = generate_referral_code(user_id)
        c.execute("INSERT INTO users (user_id, username, referral_code, referred_by) VALUES (?,?,?,?)",
                  (user_id, username, code, referred_by))
        conn.commit()
        conn.close()
        return code
    conn.close()
    return None

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_balance(user_id):
    user = get_user(user_id)
    return user[2] if user else 0.0

def get_total_earned(user_id):
    user = get_user(user_id)
    return user[3] if user else 0.0

def get_referral_count(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_active_links_count(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def add_link_to_db(user_id, original_url, short_url):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO links (user_id, original_url, short_url) VALUES (?,?,?)",
              (user_id, original_url, short_url))
    conn.commit()
    conn.close()

def update_balance_and_earnings(user_id, amount, total_earned_increment):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id=?",
              (amount, total_earned_increment, user_id))
    conn.commit()
    conn.close()

def add_referral_commission(referrer_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id=?",
              (amount, amount, referrer_id))
    conn.commit()
    conn.close()

def request_withdrawal(user_id, amount, binance_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO withdrawals (user_id, amount, binance_id) VALUES (?,?,?)",
              (user_id, amount, binance_id))
    conn.commit()
    conn.close()

def get_pending_withdrawals():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, binance_id, request_date FROM withdrawals WHERE status='pending'")
    reqs = c.fetchall()
    conn.close()
    return reqs

def update_withdrawal_status(wid, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
    conn.commit()
    conn.close()

def get_withdrawal(wid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, amount FROM withdrawals WHERE id=?", (wid,))
    row = c.fetchone()
    conn.close()
    return row

def get_all_user_ids():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_total_bot_earnings():
    """تقريب أرباح البوت = (إجمالي أرباح المستخدمين / 0.7) * 0.3"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT SUM(total_earned) FROM users")
    total = c.fetchone()[0] or 0
    conn.close()
    return total * (0.3 / 0.7)  # لأن المستخدمين يرون 70%، الباقي للبوت

# ========== لوحة /start التفاعلية ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    args = context.args

    referred_by = None
    if args:
        code = args[0]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE referral_code=?", (code,))
        ref_user = c.fetchone()
        conn.close()
        if ref_user and ref_user[0] != user_id:
            referred_by = ref_user[0]

    existing_code = register_user(user_id, username, referred_by)
    user = get_user(user_id)
    if not user:
        return await update.message.reply_text("❌ خطأ في التسجيل.")

    balance = user[2]
    total_earned = user[3]
    ref_count = get_referral_count(user_id)
    links_count = get_active_links_count(user_id)
    ref_code = user[4]
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"

    text = (
        f"👤 أهلاً بك، {username}!\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 رصيدك الحالي: {balance:.3f}$\n"
        f"📊 أرباحك الإجمالية: {total_earned:.3f}$\n"
        f"👥 عدد الإحالات: {ref_count}\n"
        f"🔗 الروابط النشطة: {links_count}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 رابط الإحالة الخاص بك:\n{ref_link}"
    )

    keyboard = [
        [InlineKeyboardButton("🔗 اختصر رابطًا", callback_data="shorten")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
         InlineKeyboardButton("👥 إحالاتي", callback_data="myreferral")],
        [InlineKeyboardButton("🏦 سحب أرباح", callback_data="withdraw"),
         InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

# ========== أزرار القائمة ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "shorten":
        await query.message.reply_text("📎 أرسل الرابط الذي تريد اختصاره:")
        return WAITING_FOR_LINK

    elif data == "balance":
        balance = get_user_balance(user_id)
        earned = get_total_earned(user_id)
        ref_count = get_referral_count(user_id)
        links_count = get_active_links_count(user_id)
        text = (
            f"💰 رصيدك الحالي: {balance:.3f}$\n"
            f"📊 أرباح إجمالية: {earned:.3f}$\n"
            f"👥 إحالات: {ref_count} | 🔗 روابط: {links_count}"
        )
        await query.edit_message_text(text)

    elif data == "myreferral":
        user = get_user(user_id)
        if user:
            code = user[4]
            bot_username = (await context.bot.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start={code}"
            await query.edit_message_text(
                f"👥 رابط الإحالة:\n{ref_link}\n\n"
                f"عند تسجيل شخص عبر هذا الرابط، ستحصل على 10% من أرباحه مدى الحياة."
            )

    elif data == "withdraw":
        user = get_user(user_id)
        if user[2] < 1.0:
            await query.edit_message_text(f"⚠️ الحد الأدنى للسحب 1$. رصيدك: {user[2]:.3f}$")
            return ConversationHandler.END
        await query.message.reply_text("🏦 أرسل معرف Binance (USDT):")
        return WAITING_FOR_BINANCE_ID

    elif data == "help":
        await query.edit_message_text(
            "ℹ️ **كيف يعمل البوت؟**\n\n"
            "1️⃣ أرسل أي رابط لاختصاره.\n"
            "2️⃣ شارك الرابط المختصر مع الآخرين.\n"
            "3️⃣ كل زيارة للرابط تربحك مالاً (يتم احتساب 70% لك، 30% للبوت).\n"
            "4️⃣ عندما يصل رصيدك 1$، يمكنك سحبه عبر Binance USDT.\n"
            "5️⃣ بدعوة أصدقائك تحصل على 10% من أرباحهم إلى الأبد.\n\n"
            "للاستفسار: تواصل مع الدعم."
        )

    return ConversationHandler.END

# ========== اختصار الرابط ==========
async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()
    if not re.match(r'https?://\S+', url) or not is_valid_url(url):
        await update.message.reply_text("❌ رابط غير صالح. أرسل رابطاً يبدأ بـ http:// أو https://")
        return WAITING_FOR_LINK

    wait_msg = await update.message.reply_text("⏳ جاري اختصار الرابط...")
    short_url = await shorten_link_api(url)
    if short_url:
        add_link_to_db(user_id, url, short_url)
        await wait_msg.edit_text(
            f"✅ تم اختصار الرابط:\n{short_url}\n\n"
            "🔁 شاركه للربح. كل زيارة = أرباح!"
        )
        return ConversationHandler.END
    else:
        await wait_msg.edit_text("❌ فشل اختصار الرابط، حاول لاحقاً.")
        return ConversationHandler.END

# ========== السحب ==========
async def receive_binance_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    binance_id = update.message.text.strip()
    if not binance_id.isdigit() or len(binance_id) < 7:
        await update.message.reply_text("❌ معرف Binance غير صالح. أعد إرساله أو /cancel للإلغاء.")
        return WAITING_FOR_BINANCE_ID

    user = get_user(user_id)
    if user[2] < 1.0:
        await update.message.reply_text("⚠️ رصيدك غير كافٍ حالياً.")
        return ConversationHandler.END

    request_withdrawal(user_id, user[2], binance_id)
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = 0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ تم طلب سحب {user[2]:.3f}$ إلى Binance ID {binance_id}.\n"
        "سيتم التحويل خلال 24 ساعة بعد المراجعة."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ألغيت العملية.")
    return ConversationHandler.END

# ========== لوحة الأدمن ==========
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات عامة", callback_data="adm_stats")],
        [InlineKeyboardButton("📤 طلبات السحب", callback_data="adm_withdrawals")],
        [InlineKeyboardButton("📢 إرسال للجميع", callback_data="adm_broadcast_prompt")]
    ]
    await update.message.reply_text("🔐 لوحة التحكم:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        return

    data = query.data
    if data == "adm_stats":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM links")
        links_count = c.fetchone()[0]
        c.execute("SELECT SUM(balance) FROM users")
        total_balance = c.fetchone()[0] or 0
        total_earned_users = c.execute("SELECT SUM(total_earned) FROM users").fetchone()[0] or 0
        bot_earnings = total_earned_users * (0.3 / 0.7)  # تقريبي
        conn.close()
        text = (
            f"👥 إجمالي المستخدمين: {users_count}\n"
            f"🔗 إجمالي الروابط: {links_count}\n"
            f"💰 أرصدة المستخدمين: {total_balance:.3f}$\n"
            f"📊 أرباح المستخدمين الظاهرة: {total_earned_users:.3f}$\n"
            f"🤖 أرباح البوت التقريبية: {bot_earnings:.3f}$"
        )
        await query.edit_message_text(text)

    elif data == "adm_withdrawals":
        requests = get_pending_withdrawals()
        if not requests:
            await query.edit_message_text("لا توجد طلبات سحب معلقة.")
            return
        msg = "📤 طلبات السحب المعلقة:\n\n"
        for req in requests:
            msg += f"🆔 {req[0]} | مستخدم {req[1]} | {req[2]:.3f}$ | Binance: {req[3]} | {req[4]}\n"
            msg += f"✅ /approve_{req[0]}  ❌ /reject_{req[0]}\n\n"
        await query.edit_message_text(msg)

    elif data == "adm_broadcast_prompt":
        await query.message.reply_text("📢 أرسل الرسالة التي تريد إرسالها للجميع:")
        context.user_data['broadcast'] = True

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS or not context.user_data.get('broadcast'):
        return
    text = update.message.text
    all_users = get_all_user_ids()
    success = 0
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 رسالة من الإدارة:\n\n{text}")
            success += 1
        except:
            pass
    await update.message.reply_text(f"✅ أُرسلت إلى {success} مستخدم.")
    context.user_data['broadcast'] = False

async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        wid = int(context.args[0])
        update_withdrawal_status(wid, "approved")
        await update.message.reply_text(f"✅ تمت الموافقة على السحب #{wid}")
    except:
        await update.message.reply_text("استخدم: /approve <رقم>")

async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        wid = int(context.args[0])
        wd = get_withdrawal(wid)
        if wd:
            # استرجاع الرصيد
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (wd[1], wd[0]))
            conn.commit()
            conn.close()
        update_withdrawal_status(wid, "rejected")
        await update.message.reply_text(f"❌ رفض السحب #{wid} وأُعيد الرصيد.")
    except:
        await update.message.reply_text("استخدم: /reject <رقم>")

# ========== مهمة تحديث الأرباح ==========
async def update_earnings_job(context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, short_url, last_earned FROM links")
    links = c.fetchall()
    for link_id, user_id, short_url, last_earned in links:
        stats = await get_link_stats(short_url)
        if not stats:
            continue
        earned = stats['earned']
        if earned <= last_earned:
            continue
        delta = earned - last_earned
        user = get_user(user_id)
        if not user:
            continue
        # توزيع الأرباح
        user_share = delta * 0.7
        referrer_id = user[5]
        if referrer_id:
            referral_share = delta * 0.1
            add_referral_commission(referrer_id, referral_share)
            update_balance_and_earnings(user_id, user_share, delta)
        else:
            update_balance_and_earnings(user_id, user_share, delta)
        c.execute("UPDATE links SET total_views=?, total_earned=?, last_earned=? WHERE id=?",
                  (stats['views'], earned, earned, link_id))
        # إشعار المستخدم إذا زاد رصيده
        if user_share > 0:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🤑 أرباح جديدة! تم إضافة {user_share:.3f}$ إلى رصيدك من الروابط."
                )
            except:
                pass
    conn.commit()
    conn.close()

# ========== التشغيل ==========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # أوامر عادية
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", lambda u,c: u.message.reply_text("استخدم /start للوحة الرئيسية.")))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("approve", approve_withdrawal))
    app.add_handler(CommandHandler("reject", reject_withdrawal))

    # محادثة اختصار الرابط + السحب
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(shorten|withdraw)$"),
            CommandHandler("shorten", lambda u,c: u.message.reply_text("أرسل الرابط للاختصار")),
            CommandHandler("withdraw", lambda u,c: u.message.reply_text("أرسل معرف Binance") if get_user_balance(u.effective_user.id)>=1 else u.message.reply_text("رصيدك أقل من 1$"))
        ],
        states={
            WAITING_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            WAITING_FOR_BINANCE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_binance_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    # أزرار القائمة الأخرى
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(balance|myreferral|help)$"))
    # أزرار الأدمن
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^adm_"))

    # البث العام
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), handle_broadcast))

    # جدولة التحديث التلقائي
    app.job_queue.run_repeating(update_earnings_job, interval=1800, first=10)

    # قائمة الأوامر
    commands = [
        BotCommand("start", "اللوحة الرئيسية"),
        BotCommand("help", "كيفية الربح"),
        BotCommand("shorten", "اختصار رابط"),
        BotCommand("withdraw", "سحب أرباح"),
        BotCommand("admin", "لوحة الأدمن")
    ]
    app.bot.set_my_commands(commands)

    app.run_polling()

if __name__ == "__main__":
    main()