import os, asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters, PreCheckoutQueryHandler
)
from config import TOKEN, ADMIN_IDS, PAYMENT_PROVIDER_TOKEN
from db import init, get_conn
from api import shorten
from earnings import update_earnings
from admin import broadcast
from referral import generate_ref_code, add_referral, get_referral_stats
from withdraw import request_withdraw
from support import support_message, reply_to_user
from points import points_system
from ads import ads_system
from admin_panel import admin_panel
from middleware import middleware

# استيراد الخدمات
from ocr import OCRProcessor
from downloader import VideoDownloader
from tts import TextToSpeech
from separator import AudioSeparator

ocr = OCRProcessor()
downloader = VideoDownloader()
tts = TextToSpeech()
separator = AudioSeparator()

WAIT_LINK, WAIT_BROADCAST, WAIT_SUPPORT = range(3)

# ---------- أوامر النقاط ----------
async def points_cmd(update, context):
    uid = update.effective_user.id
    s = points_system.get_user_stats(uid)
    r = get_referral_stats(uid)
    msg = f"⭐ نقاطك: {s['balance']}\n📊 المكتسبة: {s['total_earned']}\n💸 المنفقة: {s['total_spent']}\n\n"
    msg += f"👥 الدعوات: {r['total_invited']} (✅{r['watched_ads']} ⏳{r['pending']})\n\n"
    msg += middleware.get_service_cost_info()
    await update.message.reply_text(msg)

async def daily_cmd(update, context):
    ok, msg = points_system.claim_daily_bonus(update.effective_user.id)
    await update.message.reply_text(msg)

async def buy_points_cmd(update, context):
    pricing = points_system.get_pricing_list()
    msg = "🛒 **شراء نقاط:**\n\n"
    kb = []
    for amt, price, stars in pricing:
        msg += f"⭐ {amt} نقطة = {price:.2f}$ | ⭐{stars} نجمة\n"
        kb.append([InlineKeyboardButton(f"💰 {amt} نقطة - {price:.2f}$", callback_data=f"buy_{amt}"),
                   InlineKeyboardButton(f"⭐ {stars} نجمة", callback_data=f"stars_{amt}")])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def invite_cmd(update, context):
    uid = update.effective_user.id
    c = get_conn().cursor()
    c.execute("SELECT ref_code, referrals_count, referrals_watched_ads FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    c.connection.close()
    if row:
        bot = (await context.bot.get_me()).username
        link = f"https://t.me/{bot}?start={row[0]}"
        await update.message.reply_text(f"🔗 {link}\n👥 {row[1]} ({row[2]} شاهدوا)\n⭐ كل مشاهدة = 5 نقاط")

# ---------- الأدمن ----------
async def admin_cmd(update, context):
    if update.effective_user.id in ADMIN_IDS:
        await admin_panel.show_main_panel(update)

async def admin_callback(update, context):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in ADMIN_IDS: return
    data = q.data
    if data == "admin_stats":
        s = admin_panel.get_full_stats()
        msg = f"""📊 إحصائيات:
👥 المستخدمين: {s['total_users']} (شهر:{s['monthly_users']})
🟢 نشط اليوم: {s['active_today']} | 24س: {s['active_24h']}
📢 شاهدوا إعلان: {s['active_ads_today']}
🔗 الروابط: {s['total_links']} (اليوم:{s['today_links']})
💰 الأرباح: {s['total_earnings']:.3f}$ | الأرصدة: {s['total_balance']:.3f}$
⭐ النقاط: {s['total_points']} | مبيعات اليوم: {s['buys_count']} ({s['buys_total']})
💳 السحوبات: {s['pending_wd']} معلقة | إجمالي: {s['wd_count']} ({s['wd_total']:.3f}$)"""
        await q.message.reply_text(msg)
    elif data == "admin_adstats":
        today_views, today_ad, today_srv = ads_system.get_daily_ad_stats()
        total = ads_system.get_total_ad_stats()
        msg = f"📢 اليوم: {today_views}\n📈 الإجمالي: {total['total_views']}\n\n👥 الدعوات: {total['total_referrals']} ({total['watched_referrals']} شاهدوا)"
        await q.message.reply_text(msg)
    elif data == "admin_referrals":
        r = admin_panel.get_referral_stats()
        msg = f"👥 إجمالي: {r['total_referrals']}\n✅ شاهدوا: {r['watched_referrals']}\n⭐ نقاط: {r['awarded_referrals']}\n⏳ معلق: {r['pending_referrals']}"
        await q.message.reply_text(msg)
    elif data == "admin_withdrawals":
        c = get_conn().cursor()
        c.execute("SELECT * FROM withdraws WHERE status='pending'")
        rows = c.fetchall()
        c.connection.close()
        msg = "💳 طلبات:\n" + "\n".join(f"#{r[0]} {r[2]:.2f}$ {r[3]}" for r in rows) if rows else "لا يوجد"
        await q.message.reply_text(msg)
    elif data == "admin_points":
        info = admin_panel.get_points_management()
        msg = f"⭐ إجمالي: {info['total_balance']}\n📈 مكتسب: {info['total_earned']}\n💸 منفق: {info['total_spent']}\n🏆 الأعلى:\n"
        msg += "\n".join(f"{u[1]}: {u[2]}" for u in info['top_users'])
        await q.message.reply_text(msg)
    elif data == "admin_grant":
        await q.message.reply_text("/grant <user_id> <amount>")
    elif data == "admin_broadcast":
        await q.message.reply_text("أرسل الرسالة:")
        return WAIT_BROADCAST
    elif data == "admin_manageads":
        ads = ads_system.get_all_manual_ads()
        msg = "📝 الإعلانات:\n" + "\n".join(f"#{a['id']} {a['text'][:50]}" for a in ads)
        msg += "\n/add_ad <الوزن> <نص>"
        await q.message.reply_text(msg)
    return ConversationHandler.END

async def grant_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        target, amt = int(context.args[0]), int(context.args[1])
        points_system.admin_grant_points(update.effective_user.id, target, amt)
        await update.message.reply_text("✅ تم")
    except: await update.message.reply_text("/grant <id> <amount>")

async def add_ad_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        w = int(context.args[0])
        text = " ".join(context.args[1:])
        nid = ads_system.add_manual_ad(text, w)
        await update.message.reply_text(f"✅ أضيف #{nid}")
    except: await update.message.reply_text("/add_ad <وزن> <نص>")

async def remove_ad_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        ads_system.remove_manual_ad(int(context.args[0]))
        await update.message.reply_text("✅ حذف")
    except: await update.message.reply_text("/remove_ad <id>")

# ---------- start ----------
async def start(update, context):
    u = update.effective_user
    c = get_conn()
    cur = c.cursor()
    ref = context.args[0] if context.args else None
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,))
    if not cur.fetchone():
        new_ref = generate_ref_code()
        referrer = 0
        if ref:
            cur.execute("SELECT user_id FROM users WHERE ref_code=?", (ref,))
            rr = cur.fetchone()
            if rr: referrer = rr[0]
        cur.execute("INSERT INTO users(user_id,username,ref_code,referred_by,join_date) VALUES(?,?,?,?,?)",
                    (u.id, u.username or "user", new_ref, referrer, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if referrer:
            add_referral(u.id, referrer)
            try:
                ad_text = ads_system.show_referral_ad(u.id, referrer)
                await update.message.reply_text(f"📢 {ad_text}\n✅ تم تسجيلك")
            except: pass
    c.commit()
    cur.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (u.id,))
    links = cur.fetchone()[0]
    cur.execute("SELECT balance,total,ref_code,referrals_count,referrals_watched_ads,join_date FROM users WHERE user_id=?", (u.id,))
    bal, total, my_ref, refs, watched, join = cur.fetchone()
    c.close()
    pts = points_system.get_balance(u.id)
    bot = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot}?start={my_ref}"
    msg = f"""👋 أهلاً بك
💰 الرصيد: {bal:.3f}$ | 💵 إجمالي الأرباح: {total:.3f}$
⭐ النقاط: {pts} | 🔗 الروابط: {links}
👥 المدعوين: {refs} (✅{watched} ⏳{refs-watched})
🔗 رابط الدعوة: {ref_link}"""
    kb = [
        [InlineKeyboardButton("🔗 اختصار رابط", callback_data="short")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="bal"),
         InlineKeyboardButton("⭐ نقاطي", callback_data="points_info")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
        [InlineKeyboardButton("💳 سحب", callback_data="withdraw")],
        [InlineKeyboardButton("🔗 الدعوة", callback_data="ref"),
         InlineKeyboardButton("🛒 شراء نقاط", callback_data="buy_points_menu")],
        [InlineKeyboardButton("🎁 يومية", callback_data="daily"),
         InlineKeyboardButton("🆘 دعم", callback_data="support")],
    ]
    if u.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("🔐 لوحة الأدمن", callback_data="admin_panel")])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

# ---------- الأزرار ----------
async def button_handler(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data
    c = get_conn().cursor()
    if data == "short":
        ok, msg, _ = await middleware.check_and_process(uid, 'shorten', context)
        if not ok: await q.message.reply_text(msg); return ConversationHandler.END
        await q.message.reply_text(msg + "\n\n📎 أرسل الرابط للاختصار:")
        return WAIT_LINK
    elif data == "bal":
        c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = c.fetchone()[0]
        pts = points_system.get_balance(uid)
        await q.message.reply_text(f"💰 {bal:.3f}$ | ⭐ {pts}")
        c.connection.close(); return ConversationHandler.END
    elif data == "points_info":
        s = points_system.get_user_stats(uid)
        r = get_referral_stats(uid)
        msg = f"⭐ الرصيد: {s['balance']}\n📊 مكتسب: {s['total_earned']}\n💸 منفق: {s['total_spent']}\n\n👥 {r['total_invited']} ({r['watched_ads']} شاهدوا)\n\n" + middleware.get_service_cost_info()
        await q.message.reply_text(msg)
        c.connection.close(); return ConversationHandler.END
    elif data == "daily":
        ok, msg = points_system.claim_daily_bonus(uid)
        await q.message.reply_text(msg)
        c.connection.close(); return ConversationHandler.END
    elif data == "buy_points_menu":
        pricing = points_system.get_pricing_list()
        msg = "🛒 شراء نقاط:\n\n"
        kb = []
        for amt, price, stars in pricing:
            kb.append([InlineKeyboardButton(f"💰 {amt} نقطة - {price:.2f}$", callback_data=f"buy_{amt}"),
                       InlineKeyboardButton(f"⭐ {stars} نجمة", callback_data=f"stars_{amt}")])
        await q.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        c.connection.close(); return ConversationHandler.END
    elif data.startswith("buy_"):
        amt = int(data.split("_")[1])
        price, err = points_system.buy_points_with_money(uid, amt)
        if err: await q.message.reply_text(err)
        else: await q.message.reply_text(f"فاتورة: {amt} نقطة = {price:.2f}$\n📩 تواصل مع الأدمن للدفع")
        c.connection.close(); return ConversationHandler.END
    elif data.startswith("stars_"):
        if not PAYMENT_PROVIDER_TOKEN:
            await q.message.reply_text("❌ الدفع بالنجوم غير مفعل حالياً")
            c.connection.close(); return ConversationHandler.END
        amt = int(data.split("_")[1])
        stars_needed, err = points_system.buy_points_with_stars(uid, amt)
        if err: await q.message.reply_text(err); c.connection.close(); return ConversationHandler.END
        await context.bot.send_invoice(
            chat_id=uid,
            title="شراء نقاط",
            description=f"شراء {amt} نقطة",
            payload=f"points_{amt}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="XTR",
            prices=[LabeledPrice(label=f"{amt} نقطة", amount=stars_needed)]
        )
        c.connection.close(); return ConversationHandler.END
    elif data == "stats":
        c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (uid,))
        links = c.fetchone()[0]
        c.execute("SELECT balance,total,referrals_count,referrals_watched_ads,join_date FROM users WHERE user_id=?", (uid,))
        bal,total,refs,watched,join = c.fetchone()
        pts = points_system.get_balance(uid)
        await q.message.reply_text(f"📊 الإحصائيات:\n💰 {bal:.3f}$\n💵 {total:.3f}$\n⭐ {pts}\n🔗 {links}\n👥 {refs} ({watched} شاهدوا)\n📅 {join}")
        c.connection.close(); return ConversationHandler.END
    elif data == "ref":
        c.execute("SELECT ref_code,referrals_count,referrals_watched_ads FROM users WHERE user_id=?", (uid,))
        ref,refs,watched = c.fetchone()
        bot = (await context.bot.get_me()).username
        link = f"https://t.me/{bot}?start={ref}"
        await q.message.reply_text(f"🔗 {link}\n👥 {refs} ({watched} شاهدوا)\n⭐ كل مشاهدة = 5 نقاط")
        c.connection.close(); return ConversationHandler.END
    elif data == "admin_panel" and uid in ADMIN_IDS:
        await admin_panel.show_main_panel(q)
        c.connection.close(); return ConversationHandler.END
    elif data == "withdraw":
        await q.message.reply_text("💳 /withdraw <المبلغ> <محفظة>")
        c.connection.close(); return ConversationHandler.END
    elif data == "support":
        await q.message.reply_text("📝 أرسل رسالتك:")
        c.connection.close(); return WAIT_SUPPORT
    c.connection.close()
    return ConversationHandler.END

# ---------- خدمات إضافية ----------
async def ocr_cmd(update, context):
    uid = update.effective_user.id
    ok, msg, skip = await middleware.check_and_process(uid, 'ocr', context)
    if not ok: await update.message.reply_text(msg); return
    if not skip: await update.message.reply_text(msg)
    photo = None
    if update.message.photo: photo = update.message.photo[-1]
    elif update.message.reply_to_message and update.message.reply_to_message.photo: photo = update.message.reply_to_message.photo[-1]
    if not photo: await update.message.reply_text("📸 أرسل صورة"); return
    wait = await update.message.reply_text("🔍 جارٍ استخراج النص...")
    text = await ocr.extract_from_photo(photo)
    await wait.edit_text(f"📝 {text}" if text else "⚠️ لا يوجد نص")

async def dl_cmd(update, context):
    uid = update.effective_user.id
    ok, msg, skip = await middleware.check_and_process(uid, 'download', context)
    if not ok: await update.message.reply_text(msg); return
    if not skip: await update.message.reply_text(msg)
    if not context.args: await update.message.reply_text("📥 /dl <رابط>"); return
    url = context.args[0]
    quality = context.args[0] if context.args[0] in ['best','720','480','360','audio'] and len(context.args)>1 else 'best'
    if quality in ['best','720','480','360','audio']: url = context.args[1] if len(context.args)>1 else url
    if not downloader.is_supported(url): await update.message.reply_text("❌ غير مدعوم"); return
    wait = await update.message.reply_text("📥 جارٍ التحميل...")
    info = await downloader.get_info(url)
    if info: await wait.edit_text(f"📹 {info['title']}\n⏳ تحميل...")
    path = await downloader.download(url, quality)
    if path:
        await wait.edit_text("📤 رفع...")
        try:
            with open(path,'rb') as f:
                if quality=='audio': await update.message.reply_audio(f, title=info['title'] if info else "Audio")
                else: await update.message.reply_video(f, caption=f"✅ {info['title'] if info else 'تم'}")
        except: await wait.edit_text("❌ كبير جداً")
        os.remove(path)
        await wait.delete()
    else: await wait.edit_text("❌ فشل")

async def speak_cmd(update, context):
    uid = update.effective_user.id
    ok, msg, skip = await middleware.check_and_process(uid, 'speak', context)
    if not ok: await update.message.reply_text(msg); return
    if not skip: await update.message.reply_text(msg)
    if not context.args: await update.message.reply_text("🎙️ /speak ar_female normal النص"); return
    args = context.args
    voice = args[0] if len(args)>=3 else 'ar_female'
    speed = args[1] if len(args)>=3 else 'normal'
    text = ' '.join(args[2:]) if len(args)>=3 else ' '.join(args)
    wait = await update.message.reply_text("🎙️ تحويل...")
    path, err = await tts.convert(text, voice, speed)
    if err: await wait.edit_text(err); return
    if path:
        with open(path,'rb') as f: await update.message.reply_voice(f, caption=f"🗣 {text[:100]}")
        os.remove(path); await wait.delete()

async def separate_cmd(update, context):
    uid = update.effective_user.id
    ok, msg, skip = await middleware.check_and_process(uid, 'separate', context)
    if not ok: await update.message.reply_text(msg); return
    if not skip: await update.message.reply_text(msg)
    if not (update.message.audio or update.message.voice): await update.message.reply_text("🎵 أرسل ملفاً صوتياً"); return
    wait = await update.message.reply_text("🎵 فصل...")
    file = update.message.audio or update.message.voice
    tmp = f"temp_{os.urandom(4).hex()}.mp3"
    await file.download_to_drive(tmp)
    res, err = await separator.separate(tmp)
    if err: await wait.edit_text(err); os.remove(tmp); return
    if res:
        await wait.edit_text("📤 إرسال...")
        for k, path in res.items():
            with open(path,'rb') as f: await update.message.reply_audio(f, caption=f"🎤 {k}")
            os.remove(path)
        await wait.delete()
    os.remove(tmp)

async def link(update, context):
    url = update.message.text
    await update.message.reply_text("⏳ اختصار...")
    short = await shorten(url)
    if not short: await update.message.reply_text("❌ فشل"); return ConversationHandler.END
    c = get_conn()
    c.cursor().execute("INSERT INTO links(user_id,original_url,short,created_at) VALUES(?,?,?,?)",
                       (update.effective_user.id, url, short, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit(); c.close()
    await update.message.reply_text(f"✅ {short}")
    return ConversationHandler.END

async def bc(update, context):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    ok, fail = await broadcast(context.bot, update.message.text)
    await update.message.reply_text(f"✅ نجاح:{ok} فشل:{fail}")
    return ConversationHandler.END

async def support_msg(update, context):
    await support_message(update, context)
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("❌ ألغيت"); return ConversationHandler.END

# ---------- معالج الدفع بالنجوم ----------
async def pre_checkout_callback(update, context):
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("points_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="خطأ في الطلب")

async def successful_payment_callback(update, context):
    payment = update.message.successful_payment
    if payment.invoice_payload.startswith("points_"):
        amt = int(payment.invoice_payload.split("_")[1])
        points_system.add_points(update.effective_user.id, amt, 'buy_stars', f'شراء {amt} نقطة بالنجوم')
        await update.message.reply_text(f"✅ تم شراء {amt} نقطة بنجاح! شكراً لدفعك.")

async def job(context):
    await update_earnings(context.bot)

def main():
    init()
    points_system.init_tables()
    ads_system.init_tables()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^(short|support)$")],
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
    app.add_handler(CommandHandler("points", points_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("buy_points", buy_points_cmd))
    app.add_handler(CommandHandler("invite", invite_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("grant", grant_cmd))
    app.add_handler(CommandHandler("add_ad", add_ad_cmd))
    app.add_handler(CommandHandler("remove_ad", remove_ad_cmd))
    app.add_handler(CommandHandler("ocr", ocr_cmd))
    app.add_handler(CommandHandler("dl", dl_cmd))
    app.add_handler(CommandHandler("speak", speak_cmd))
    app.add_handler(CommandHandler("separate", separate_cmd))
    app.add_handler(CommandHandler("vocal", separate_cmd))
    app.add_handler(CommandHandler("music", separate_cmd))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(bal|stats|ref|withdraw|points_info|daily|buy_points_menu)$"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^stars_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(conv)
    if PAYMENT_PROVIDER_TOKEN:
        app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.job_queue.run_repeating(job, interval=1800, first=10)
    print("✅ البوت يعمل")
    app.run_polling()

if __name__ == "__main__":
    main()