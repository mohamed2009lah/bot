from db import get_conn
from config import ADMIN_IDS
from datetime import datetime

async def support_message(update, context):
    user_id = update.effective_user.id
    msg = update.message.text

    c = get_conn()
    cursor = c.cursor()
    cursor.execute("INSERT INTO support_tickets(user_id, message, created_at) VALUES(?,?,?)",
                   (user_id, msg, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    ticket_id = cursor.lastrowid
    c.commit()
    username = update.effective_user.username or "بدون معرف"

    # معلومات إضافية
    cursor.execute("SELECT balance, referrals_count FROM users WHERE user_id=?", (user_id,))
    user_info = cursor.fetchone()
    
    try:
        from points import points_system
        points_balance = points_system.get_balance(user_id)
    except:
        points_balance = 0

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"📩 **رسالة دعم #{ticket_id}**\n"
                f"👤 المستخدم: {username} ({user_id})\n"
                f"💰 الرصيد: {user_info[0]:.3f}$\n"
                f"⭐ النقاط: {points_balance}\n"
                f"👥 المدعوين: {user_info[1]}\n"
                f"📝 الرسالة: {msg}\n\n"
                f"للرد: `/reply {ticket_id} <الرد>`"
            )
        except:
            pass

    await update.message.reply_text("✅ تم إرسال رسالتك للإدارة، سنرد عليك قريباً")
    c.close()

async def reply_to_user(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ هذا الأمر للإدارة فقط")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ استخدم: /reply <رقم التذكرة> <الرد>")
        return

    try:
        ticket_id = int(args[0])
    except:
        await update.message.reply_text("❌ رقم تذكرة غير صالح")
        return

    reply_text = " ".join(args[1:])

    c = get_conn().cursor()
    c.execute("SELECT user_id FROM support_tickets WHERE id=? AND status='open'", (ticket_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text("❌ التذكرة غير موجودة أو تم الرد عليها مسبقاً")
        c.connection.close()
        return

    target_user = row[0]
    c.execute("UPDATE support_tickets SET reply=?, status='closed' WHERE id=?", (reply_text, ticket_id))
    c.connection.commit()
    c.connection.close()

    try:
        await context.bot.send_message(
            target_user,
            f"📬 **رد الإدارة على تذكرتك #{ticket_id}:**\n\n{reply_text}\n\n"
            f"🆘 إذا احتجت مساعدة إضافية، تواصل معنا مجدداً"
        )
        await update.message.reply_text(f"✅ تم إرسال الرد للمستخدم {target_user}")
    except:
        await update.message.reply_text("⚠️ تم حفظ الرد لكن تعذر إرساله للمستخدم (قد يكون حظر البوت)")
