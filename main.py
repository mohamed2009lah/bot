import asyncio
import os
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

# الملفات الجديدة
from ocr import OCRProcessor
from downloader import VideoDownloader
from tts import TextToSpeech
from separator import AudioSeparator
from points import PointsSystem
from ads import AdsSystem
from admin_panel import AdminPanel
from middleware import Middleware

# تهيئة الأنظمة
ocr = OCRProcessor()
downloader = VideoDownloader()
tts = TextToSpeech()
separator = AudioSeparator()
points_system = PointsSystem()
ads_system = AdsSystem()
admin_panel = AdminPanel()
middleware = Middleware()

WAIT_LINK, WAIT_BROADCAST, WAIT_SUPPORT = range(3)

# ========== نظام النقاط ==========
async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رصيد النقاط"""
    user_id = update.effective_user.id
    stats = points_system.get_user_stats(user_id)
    
    msg = f"⭐ **نقاطك:**\n\n"
    msg += f"💰 الرصيد: {stats['balance']} نقطة\n"
    msg += f"📊 المكتسبة: {stats['total_earned']} نقطة\n"
    msg += f"💸 المنفقة: {stats['total_spent']} نقطة\n\n"
    msg += middleware.get_service_cost_info()
    
    await update.message.reply_text(msg)


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المكافأة اليومية"""
    user_id = update.effective_user.id
    success, msg = points_system.claim_daily_bonus(user_id)
    await update.message.reply_text(msg)


async def buy_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شراء نقاط"""
    pricing = points_system.get_pricing_list()
    
    msg = "🛒 **شراء نقاط:**\n\n"
    keyboard = []
    
    for amount, price in pricing:
        msg += f"⭐ {amount} نقطة = {price:.2f}$\n"
        keyboard.append([InlineKeyboardButton(
            f"شراء {amount} نقطة - {price:.2f}$",
            callback_data=f"buy_{amount}"
        )])
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رابط الدعوة"""
    user_id = update.effective_user.id
    c = get_conn().cursor()
    c.execute("SELECT ref_code, referrals_count FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    c.connection.close()
    
    if row:
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={row[0]}"
        
        msg = f"🔗 **رابط الدعوة:**\n{ref_link}\n\n"
        msg += f"👥 عدد المدعوين: {row[1]}\n"
        msg += f"⭐ كل صديق = 5 نقاط!\n\n"
        msg += "📢 شارك رابطك واربح نقاطاً مجانية"
        
        await update.message.reply_text(msg)


# ========== لوحة الأدمن ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة الأدمن"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    await admin_panel.show_main_panel(update)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار الأدمن"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id not in ADMIN_IDS:
        return
    
    data = q.data
    
    if data == "admin_stats":
        stats = admin_panel.get_bot_stats()
        msg = f"""
📊 **إحصائيات البوت:**

👥 إجمالي المستخدمين: {stats['total_users']}
📅 مستخدمي الشهر: {stats['monthly_users']}
🟢 نشط اليوم: {stats['active_today']}
🟡 نشط 24 ساعة: {stats['active_24h']}

🔗 الروابط: {stats['total_links']}
💰 الأرباح: {stats['total_earnings']:.2f}$
⭐ النقاط: {stats['total_points']}

💳 السحوبات: {stats['wd_count']} ({stats['wd_total']:.2f}$)
"""
        await q.message.reply_text(msg)
    
    elif data == "admin_withdrawals":
        c = get_conn().cursor()
        c.execute("""
        SELECT id, user_id, amount, wallet, request_date 
        FROM withdraws 
        WHERE status='pending' 
        ORDER BY request_date DESC
        """)
        rows = c.fetchall()
        c.connection.close()
        
        if rows:
            msg = "💳 **طلبات السحب:**\n\n"
            for r in rows:
                msg += f"🆔 {r[0]} | 👤 {r[1]} | 💰 {r[2]:.2f}$ | 🏦 {r[3]}\n"
                msg += f"📅 {r[4]}\n\n"
        else:
            msg = "لا توجد طلبات سحب معلقة"
        
        await q.message.reply_text(msg)
    
    elif data == "admin_points":
        info = admin_panel.get_points_management()
        msg = f"""
⭐ **إدارة النقاط:**

📊 إجمالي النقاط: {info['total_balance']}
📈 المكتسبة: {info['total_earned']}
💸 المنفقة: {info['total_spent']}
🛒 مبيعات اليوم: {info['buys_count']} ({info['buys_total']} نقطة)

🏆 **الأكثر نقاطاً:**
"""
        for i, u in enumerate(info['top_users'], 1):
            msg += f"{i}. {u[1]} - {u[2]} نقطة\n"
        
        await q.message.reply_text(msg)
    
    elif data == "admin_grant":
        await q.message.reply_text(
            "👤 لمنح نقاط:\n/grant <user_id> <amount>\n\n"
            "مثال: /grant 123456789 50"
        )
    
    elif data == "admin_broadcast":
        await q.message.reply_text("📢 أرسل الرسالة للإرسال للجميع:")
        return WAIT_BROADCAST
    
    elif data == "admin_adstats":
        total_views, ad_stats = ads_system.get_ad_stats()
        msg = f"📈 **إحصائيات الإعلانات:**\n\n"
        msg += f"👁 المشاهدات: {total_views}\n\n"
        for ad_id, views in ad_stats:
            msg += f"📢 إعلان {ad_id}: {views} مشاهدة\n"
        
        await q.message.reply_text(msg)
    
    return ConversationHandler.END


async def grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منح نقاط لمستخدم"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ استخدم: /grant <user_id> <amount>")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except:
        await update.message.reply_text("❌ بيانات غير صالحة")
        return
    
    points_system.admin_grant_points(update.effective_user.id, target_id, amount)
    await update.message.reply_text(f"✅ تم منح {amount} نقطة للمستخدم {target_id}")


# ========== تعديل start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = get_conn()
    cursor = c.cursor()

    ref_code = None
    if context.args:
        ref_code = context.args[0]

    cursor.execute("SELECT user_id, ref_code FROM users WHERE user_id=?", (u.id,))
    existing = cursor.fetchone()

    if not existing:
        new_ref = generate_ref_code()
        referrer_id = 0

        if ref_code:
            cursor.execute("SELECT user_id FROM users WHERE ref_code=?", (ref_code,))
            ref_row = cursor.fetchone()
            if ref_row:
                referrer_id = ref_row[0]

        cursor.execute("INSERT INTO users(user_id, username, ref_code, referred_by, join_date) VALUES(?,?,?,?,?)",
                       (u.id, u.username or "user", new_ref, referrer_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        if referrer_id != 0:
            add_referral(u.id, referrer_id)

    c.commit()

    cursor.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (u.id,))
    links_count = cursor.fetchone()[0]

    cursor.execute("SELECT balance, total, ref_code, referrals_count, join_date FROM users WHERE user_id=?", (u.id,))
    bal, total, my_ref, refs_count, join_date = cursor.fetchone()
    c.close()

    # رصيد النقاط
    points_balance = points_system.get_balance(u.id)

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={my_ref}"

    msg = f"""
👋 أهلاً بك في LinkEarn Bot

📊 **إحصائياتك:**
💰 الرصيد: {bal:.3f}$
💵 إجمالي الأرباح: {total:.3f}$
⭐ رصيد النقاط: {points_balance}
🔗 عدد الروابط: {links_count}
👥 عدد المدعوين: {refs_count}
📅 تاريخ التسجيل: {join_date}

🔗 رابط الدعوة:
{ref_link}

📌 شارك رابطك لتربح 10% من أرباح + 5 نقاط لكل مدعو!
"""

    kb = [
        [InlineKeyboardButton("🔗 اختصار رابط", callback_data="short")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="bal"),
         InlineKeyboardButton("⭐ نقاطي", callback_data="points_info")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
        [InlineKeyboardButton("💳 سحب", callback_data="withdraw")],
        [InlineKeyboardButton("🔗 رابط الدعوة", callback_data="ref"),
         InlineKeyboardButton("🛒 شراء نقاط", callback_data="buy_points")],
        [InlineKeyboardButton("🎁 المكافأة اليومية", callback_data="daily")],
        [InlineKeyboardButton("🆘 دعم", callback_data="support")],
    ]

    if u.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("🔐 لوحة الأدمن", callback_data="admin_panel")])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))


# ========== تعديل button_handler ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    c = get_conn().cursor()

    if q.data == "short":
        # التحقق من النقاط قبل الخدمة
        allowed, msg, _ = await middleware.check_and_process(uid, 'shorten', context)
        if not allowed:
            await q.message.reply_text(msg)
            return ConversationHandler.END
        await q.message.reply_text(msg + "\n\n📎 أرسل الرابط الذي تريد اختصاره:")
        return WAIT_LINK

    elif q.data == "bal":
        c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = c.fetchone()[0]
        points = points_system.get_balance(uid)
        await q.message.reply_text(f"💰 رصيدك: {bal:.3f}$\n⭐ نقاطك: {points}\n💳 الحد الأدنى للسحب: 2$")
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "points_info":
        stats = points_system.get_user_stats(uid)
        msg = f"⭐ **نقاطك:**\n💰 الرصيد: {stats['balance']}\n📊 المكتسبة: {stats['total_earned']}\n💸 المنفقة: {stats['total_spent']}\n\n"
        msg += middleware.get_service_cost_info()
        await q.message.reply_text(msg)
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "daily":
        success, msg = points_system.claim_daily_bonus(uid)
        await q.message.reply_text(msg)
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "buy_points":
        pricing = points_system.get_pricing_list()
        msg = "🛒 **شراء نقاط:**\n\n"
        kb = []
        for amount, price in pricing:
            msg += f"⭐ {amount} نقطة = {price:.2f}$\n"
            kb.append([InlineKeyboardButton(f"{amount} نقطة - {price:.2f}$", callback_data=f"buy_{amount}")])
        await q.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        c.connection.close()
        return ConversationHandler.END

    elif q.data.startswith("buy_"):
        amount = int(q.data.replace("buy_", ""))
        price, error = points_system.buy_points(uid, amount)
        if error:
            await q.message.reply_text(error)
        else:
            await q.message.reply_text(
                f"🛒 **فاتورة شراء نقاط:**\n\n"
                f"⭐ النقاط: {amount}\n"
                f"💵 السعر: {price:.2f}$\n\n"
                f"📩 تواصل مع @admin للدفع وإتمام الشراء"
            )
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "stats":
        c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (uid,))
        links_count = c.fetchone()[0]
        c.execute("SELECT balance, total, referrals_count, join_date FROM users WHERE user_id=?", (uid,))
        bal, total, refs, date = c.fetchone()
        points = points_system.get_balance(uid)
        await q.message.reply_text(f"""
📊 إحصائياتك:
💰 الرصيد: {bal:.3f}$
💵 إجمالي الأرباح: {total:.3f}$
⭐ رصيد النقاط: {points}
🔗 الروابط: {links_count}
👥 المدعوين: {refs}
📅 عضو منذ: {date}
        """)
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "ref":
        c.execute("SELECT ref_code, referrals_count FROM users WHERE user_id=?", (uid,))
        ref, refs = c.fetchone()
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={ref}"
        await q.message.reply_text(
            f"🔗 رابط الدعوة:\n{ref_link}\n\n"
            f"👥 المدعوين: {refs}\n"
            f"⭐ كل صديق = 5 نقاط!\n"
            f"💰 + 10% من أرباح المدعوين"
        )
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "admin_panel" and uid in ADMIN_IDS:
        await admin_panel.show_main_panel(q)
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "withdraw":
        await q.message.reply_text("💳 لطلب السحب:\nاستخدم الأمر:\n/withdraw <المبلغ> <عنوان Binance>\n\n📌 الحد الأدنى: 2$")
        c.connection.close()
        return ConversationHandler.END

    elif q.data == "support":
        await q.message.reply_text("📝 أرسل رسالتك وسيتم إرسالها للإدارة:")
        c.connection.close()
        return WAIT_SUPPORT

    c.connection.close()
    return ConversationHandler.END


# ========== أوامر الخدمات الجديدة (مع التحقق من النقاط) ==========
async def ocr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    allowed, msg, skip = await middleware.check_and_process(uid, 'ocr', context)
    
    if not allowed:
        await update.message.reply_text(msg)
        return
    
    if not skip:
        await update.message.reply_text(msg)
    
    if not update.message.photo and not update.message.reply_to_message:
        await update.message.reply_text("📸 أرسل صورة مع الأمر /ocr")
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
    elif update.message.photo:
        photo = update.message.photo[-1]
    else:
        await update.message.reply_text("❌ لم يتم العثور على صورة")
        return
    
    wait = await update.message.reply_text("🔍 جاري استخراج النص...")
    text = await ocr.extract_from_photo(photo)
    
    if text:
        await wait.edit_text(f"📝 **النص المستخرج:**\n\n{text}")
    else:
        await wait.edit_text("⚠️ لم يتم العثور على نص في الصورة")


async def dl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    allowed, msg, skip = await middleware.check_and_process(uid, 'download', context)
    
    if not allowed:
        await update.message.reply_text(msg)
        return
    
    if not skip:
        await update.message.reply_text(msg)
    
    if not context.args:
        await update.message.reply_text("📥 استخدم: /dl <رابط الفيديو>\n/d

l 720 <رابط>")
        return
    
    quality = 'best'
    url = context.args[0]
    if len(context.args) > 1 and context.args[0] in ['best', '720', '480', '360', 'audio']:
        quality = context.args[0]
        url = context.args[1]
    
    if not downloader.is_supported(url):
        await update.message.reply_text("❌ هذا الموقع غير مدعوم")
        return
    
    wait = await update.message.reply_text("📥 جاري التحميل...")
    info = await downloader.get_info(url)
    if info:
        await wait.edit_text(f"📹 {info['title']}\n⏳ جاري التحميل...")
    
    file_path = await downloader.download(url, quality)
    
    if file_path:
        await wait.edit_text("📤 جاري رفع الملف...")
        try:
            with open(file_path, 'rb') as f:
                if quality == 'audio':
                    await update.message.reply_audio(audio=f, title=info['title'] if info else "Audio")
                else:
                    await update.message.reply_video(video=f, caption=f"✅ {info['title'] if info else 'تم'}")
        except:
            await wait.edit_text(f"❌ الملف كبير. جرب /dl 480 {url}")
        os.remove(file_path)
        await wait.delete()
    else:
        await wait.edit_text("❌ فشل التحميل")


async def speak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    allowed, msg, skip = await middleware.check_and_process(uid, 'speak', context)
    
    if not allowed:
        await update.message.reply_text(msg)
        return
    
    if not skip:
        await update.message.reply_text(msg)
    
    if not context.args:
        await update.message.reply_text("🎙️ استخدم: /speak ar_female normal النص")
        return
    
    args = context.args
    if len(args) >= 3:
        voice, speed, text = args[0], args[1], ' '.join(args[2:])
    else:
        voice, speed, text = 'ar_female', 'normal', ' '.join(args)
    
    wait = await update.message.reply_text("🎙️ جاري التحويل...")
    file_path, error = await tts.convert(text, voice, speed)
    
    if error:
        await wait.edit_text(error)
        return
    
    if file_path:
        with open(file_path, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=f"🗣 {text[:100]}")
        os.remove(file_path)
        await wait.delete()


async def separate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    allowed, msg, skip = await middleware.check_and_process(uid, 'separate', context)
    
    if not allowed:
        await update.message.reply_text(msg)
        return
    
    if not skip:
        await update.message.reply_text(msg)
    
    if not update.message.audio and not update.message.voice:
        await update.message.reply_text("🎵 أرسل ملف صوتي مع /separate")
        return
    
    wait = await update.message.reply_text("🎵 جاري فصل الصوت...")
    file = update.message.audio or update.message.voice
    temp_path = f"temp_{os.urandom(4).hex()}.mp3"
    await file.download_to_drive(temp_path)
    
    result, error = await separator.separate(temp_path)
    
    if error:
        await wait.edit_text(error)
        if os.path.exists(temp_path): os.remove(temp_path)
        return
    
    if result:
        await wait.edit_text("📤 جاري الإرسال...")
        if 'vocals' in result:
            with open(result['vocals'], 'rb') as f:
                await update.message.reply_audio(audio=f, caption="🎤 الصوت")
            os.remove(result['vocals'])
        if 'music' in result:
            with open(result['music'], 'rb') as f:
                await update.message.reply_audio(audio=f, caption="🎵 الموسيقى")
            os.remove(result['music'])
        await wait.delete()
    
    if os.path.exists(temp_path): os.remove(temp_path)


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    await update.message.reply_text("⏳ جاري الاختصار...")
    
    short_url = await shorten(url)
    
    if not short_url:
        await update.message.reply_text("❌ فشل اختصار الرابط")
        return ConversationHandler.END
    
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("INSERT INTO links(user_id, original_url, short, created_at) VALUES(?,?,?,?)",
                   (update.effective_user.id, url, short_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit()
    c.close()
    
    await update.message.reply_text(f"✅ تم الاختصار:\n{short_url}")
    return ConversationHandler.END


async def bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    ok, fail = await broadcast(context.bot, update.message.text)
    await update.message.reply_text(f"✅ تم الإرسال\n✔ نجاح: {ok}\n❌ فشل: {fail}")
    return ConversationHandler.END


async def support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await support_message(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END


async def job(context: ContextTypes.DEFAULT_TYPE):
    await update_earnings(context.bot)


def main():
    init()
    points_system.init_tables()
    ads_system.init_tables()
    
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(short|support)$"),
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
    
    # أوامر النقاط
    app.add_handler(CommandHandler("points", points_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("buy_points", buy_points_command))
    app.add_handler(CommandHandler("invite", invite_command))
    
    # أوامر الأدمن
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("grant", grant_command))
    
    # أوامر الخدمات
    app.add_handler(CommandHandler("ocr", ocr_command))
    app.add_handler(CommandHandler("ocrurl", ocr_command))
    app.add_handler(CommandHandler("dl", dl_command))
    app.add_handler(CommandHandler("speak", speak_command))
    app.add_handler(CommandHandler("separate", separate_command))
    app.add_handler(CommandHandler("vocal", separate_command))
    app.add_handler(CommandHandler("music", separate_command))
    
    # أزرار
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(bal|stats|ref|withdraw|points_info|daily|buy_points)$"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(conv)
    
    app.job_queue.run_repeating(job, interval=1800, first=10)
    
    print("✅ البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
