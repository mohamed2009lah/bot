import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import TOKEN, ADMIN_IDS
from db import init, conn
from api import shorten
from earnings import update_earnings
from admin import broadcast

WAIT_LINK, WAIT_BROADCAST = range(2)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user

    c = conn().cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,username) VALUES(?,?)",
              (u.id, u.username or "user"))
    conn().commit()

    kb = [
        [InlineKeyboardButton("🔗 اختصار", callback_data="short")],
        [InlineKeyboardButton("💰 رصيد", callback_data="bal")]
    ]

    if u.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("📢 إرسال إعلان", callback_data="adm")])

    await update.message.reply_text(
        "👋 أهلاً بك",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= CALLBACK =================
async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "short":
        await q.message.reply_text("📎 أرسل الرابط")
        return WAIT_LINK

    if q.data == "bal":
        c = conn().cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = c.fetchone()[0]
        await q.edit_message_text(f"💰 رصيدك: {bal:.3f}$")
        return ConversationHandler.END

    if q.data == "adm" and uid in ADMIN_IDS:
        await q.message.reply_text("📢 أرسل الرسالة")
        return WAIT_BROADCAST

# ================= LINK =================
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    short = await shorten(url)

    if not short:
        await update.message.reply_text("❌ فشل")
        return ConversationHandler.END

    c = conn().cursor()
    c.execute("INSERT INTO links(user_id,short) VALUES(?,?)",
              (update.effective_user.id, short))
    conn().commit()

    await update.message.reply_text(f"✅ تم:\n{short}")
    return ConversationHandler.END

# ================= BROADCAST =================
async def bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    ok, fail = await broadcast(context.bot, update.message.text)

    await update.message.reply_text(
        f"✅ تم الإرسال\n✔ {ok}\n❌ {fail}"
    )

# ================= JOB =================
async def job(context: ContextTypes.DEFAULT_TYPE):
    await update_earnings(context.bot)

# ================= MAIN =================
def main():
    init()

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb)],
        states={
            WAIT_LINK: [MessageHandler(filters.TEXT, link)],
            WAIT_BROADCAST: [MessageHandler(filters.TEXT, bc)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    app.job_queue.run_repeating(job, interval=1800, first=10)

    app.run_polling()

if __name__ == "__main__":
    main()
