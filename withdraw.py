from db import get_conn
from config import ADMIN_IDS, MIN_WITHDRAW
from datetime import datetime

async def request_withdraw(update, context):
    user_id = update.effective_user.id
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            f"❌ استخدم: /withdraw <المبلغ> <عنوان Binance>\n\n"
            f"📌 الحد الأدنى: {MIN_WITHDRAW}$"
        )
        return

    try:
        amount = float(args[0])
    except:
        await update.message.reply_text("❌ مبلغ غير صالح")
        return

    wallet = args[1]
    min_withdraw = MIN_WITHDRAW

    c = get_conn().cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    balance = row[0] if row else 0

    if amount < min_withdraw:
        await update.message.reply_text(f"❌ الحد الأدنى للسحب: {min_withdraw}$")
        c.connection.close()
        return

    if amount > balance:
        await update.message.reply_text(f"❌ رصيدك غير كافٍ. رصيدك: {balance:.3f}$")
        c.connection.close()
        return

    # إنشاء طلب السحب
    c.execute("INSERT INTO withdraws(user_id, amount, wallet, request_date) VALUES(?,?,?,?)",
              (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    c.connection.commit()

    # معلومات إضافية للإدارة
    c.execute("SELECT username, join_date, referrals_count FROM users WHERE user_id=?", (user_id,))
    user_info = c.fetchone()
    c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (user_id,))
    links_count = c.fetchone()[0]
    c.execute("SELECT SUM(earned) FROM links WHERE user_id=?", (user_id,))
    total_from_links = c.fetchone()[0] or 0
    
    # رصيد النقاط
    try:
        from points import points_system
        points_balance = points_system.get_balance(user_id)
    except:
        points_balance = 0
    
    c.connection.close()

    # إرسال إشعار للإدارة
    admin_msg = f"""
📥 **طلب سحب جديد**

👤 المستخدم: {user_info[0]} ({user_id})
💰 المبلغ: {amount:.3f}$
🏦 المحفظة: `{wallet}`
📅 تاريخ التسجيل: {user_info[1]}
🔗 عدد الروابط: {links_count}
👥 عدد المدعوين: {user_info[2]}
💵 أرباح الروابط: {total_from_links:.3f}$
⭐ رصيد النقاط: {points_balance}

للموافقة: `/approve_{user_id}_{amount}`
للرفض: `/reject_{user_id}_{amount}`
    """

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_msg)
        except:
            pass

    await update.message.reply_text(
        f"✅ **تم تقديم طلب السحب**\n\n"
        f"💰 المبلغ: {amount:.3f}$\n"
        f"🏦 المحفظة: `{wallet}`\n"
        f"📌 سيتم المراجعة خلال 24 ساعة"
        )
