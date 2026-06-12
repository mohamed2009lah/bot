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
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, f"📩 تذكرة #{ticket_id}\n👤 {username} ({user_id})\n📝 {msg}\n\nللرد: /reply {ticket_id} <الرد>")
        except:
            pass
    
    await update.message.reply_text("✅ تم إرسال رسالتك للإدارة")
    c.close()

async def reply_to_user(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
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
        await update.message.reply_text("❌ التذكرة غير موجودة أو تم الرد عليها")
        c.connection.close()
        return
    
    target_user = row[0]
    c.execute("UPDATE support_tickets SET reply=?, status='closed' WHERE id=?", (reply_text, ticket_id))
    c.connection.commit()
    c.connection.close()
    
    try:
        await context.bot.send_message(target_user, f"📬 رد الإدارة على تذكرتك #{ticket_id}:\n\n{reply_text}")
        await update.message.reply_text("✅ تم إرسال الرد")
    except:
        await update.message.reply_text("⚠️ تم حفظ الرد لكن تعذر إرساله للمستخدم")
