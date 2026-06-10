import asyncio
from datetime import datetime
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
from db import init, get_conn
from api import shorten
from earnings import update_earnings
from admin import broadcast
from referral import generate_ref_code, add_referral
from withdraw import request_withdraw
from support import support_message, reply_to_user

WAIT_LINK, WAIT_BROADCAST, WAIT_SUPPORT = range(3)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = get_conn()
    cursor = c.cursor()

    # التحقق من الإحالة
    ref_code = None
    if context.args:
        ref_code = context.args[0]

    cursor.execute("SELECT user_id, ref_code FROM users WHERE user_id=?", (u.id,))
    existing = cursor.fetchone()

    if not existing:
        # مستخدم جديد
        new_ref = generate_ref_code()
        referrer_id = 0

        if ref_code:
            cursor.execute("SELECT user_id FROM users WHERE ref_code=?", (ref_code,))
            ref_row = cursor.fetchone()
            if ref_row:
                referrer_id = ref_row[0]

        cursor.execute("""
        INSERT INTO users(user_id, username, ref_code, referred_by, join_date)
        VALUES(?,?,?,?,?)
        """, (u.id, u.username or "user", new_ref, referrer_id,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        if referrer_id != 0:
            add_referral(u.id, referrer_id)

    c.commit()

    # جلب الإحصائيات
    cursor.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (u.id,))
    links_count = cursor.fetchone()[0]

    cursor.execute("SELECT balance, total, ref_code, referrals_count, join_date FROM users WHERE user_id=?", (u.id,))
    bal, total, my_ref, refs_count, join_date = cursor.fetchone()
    c.close()

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={my_ref}"

    msg = f"""
👋 **أهلاً بك في LinkEarn Bot**

📊 **إحصائياتك:**
💰 الرصيد الحالي: **{bal:.3f}$**
💵 إجمالي الأرباح: **{total:.3f}$**
🔗 عدد الروابط: **{links_count}**
👥 عدد المدعوين: **{refs_count}**
📅 تاريخ التسجيل: **{join_date}**

🔗 **رابط الدعوة الخاص بك:**
`{ref_link}`

📌 **شارك رابطك لتربح 10% من أرباح من يدعوهم!**
"""

    kb = [
        [InlineKeyboardButton("🔗 اختصار رابط", callback_data="short")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="bal")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
        [InlineKeyboardButton("💳 سحب", callback_data="withdraw")],
        [InlineKeyboardButton("🔗 رابط الدعوة", callback_data="ref")],
        [InlineKeyboardButton("🆘 دعم", callback_data="support")],
    ]

    if u.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("📢 إرسال إعلان", callback_data="adm")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    c = get_conn().cursor()

    if q.data == "short":
        await q.message.reply_text("📎 أرسل الرابط الذي تريد اختصاره:")
        return WAIT_LINK

    elif q.data == "bal":
        c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = c.fetchone()[0]
        await q.message.reply_text(f"💰 رصيدك الحالي: **{bal:.3f}$**\n💳 الحد الأدنى للسحب: 2$")
        return ConversationHandler.END

    elif q.data == "stats":
        c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (uid,))
        links_count = c.fetchone()[0]
        c.execute("SELECT balance, total, referrals_count, join_date FROM users WHERE user_id=?", (uid,))
        bal, total, refs, date = c.fetchone()
        
        stats_msg = f"""
📊 **إحصائياتك:**
💰 الرصيد: {bal:.3f}$
💵 إجمالي الأرباح: {total:.3f}$
🔗 الروابط: {links_count}
👥 المدعوين: {refs}
📅 عضو منذ: {date}
        """
        await q.message.reply_text(stats_msg)
        return ConversationHandler.END

    elif q.data == "ref":
        c.execute("SELECT ref_code FROM users WHERE user_id=?", (uid,))
        ref = c.fetchone()[0]
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={ref}"
        await q.message.reply_text(
            f"🔗 **رابط الدعوة الخاص بك:**\n`{ref_link}`\n\n📌 شاركه لتربح 10% من أرباح كل من يسجل عبره!"
        )
        return ConversationHandler.END

    elif q.data == "withdraw":
        await q.message.reply_text(
            "💳 **لطلب السحب:**\nاستخدم الأمر:\n`/withdraw <المبلغ> <عنوان Binance>`\n\n📌 الحد الأدنى: 2$"
        )
        return ConversationHandler.END

    elif q.data == "support":
        await q.message.reply_text("📝 أرسل رسالتك وسيتم إرسالها للإدارة:")
        return WAIT_SUPPORT

    elif q.data == "adm" and uid in ADMIN_IDS:
        await q.message.reply_text("📢 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
        return WAIT_BROADCAST

    c.connection.close()
    return ConversationHandler.END

# ================= LINK =================
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    await update.message.reply_text("⏳ جاري الاختصار...")
    
    short_url = await shorten(url)

    if not short_url:
        await update.message.reply_text("❌ فشل اختصار الرابط، تأكد من صحة الرابط")
        return ConversationHandler.END

    c = get_conn()
    cursor = c.cursor()
    cursor.execute("INSERT INTO links(user_id, original_url, short, created_at) VALUES(?,?,?,?)",
              (update.effective_user.id, url, short_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit()
    c.close()

    await update.message.reply_text(f"✅ **تم الاختصار:**\n{short_url}")
    return ConversationHandler.END

# ================= BROADCAST =================
async def bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    ok, fail = await broadcast(context.bot, update.message.text)
    await update.message.reply_text(f"✅ تم الإرسال\n✔ نجاح: {ok}\n❌ فشل: {fail}")
    return ConversationHandler.END

# ================= SUPPORT =================
async def support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await support_message(update, context)
    return ConversationHandler.END

# ================= CANCEL =================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

# ================= JOB =================
async def job(context: ContextTypes.DEFAULT_TYPE):
    await update_earnings(context.bot)

# ================= MAIN =================
def main():
    init()

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(short|adm|support)$")
        ],
        states={
            WAIT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link)],
            WAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, bc)],
            WAIT_SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_msg)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("withdraw", request_withdraw))
    app.add_handler(CommandHandler("reply", reply_to_user))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(bal|stats|ref|withdraw)$"))
    app.add_handler(conv)

    app.job_queue.run_repeating(job, interval=1800, first=10)

    print("✅ البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
