from db import get_conn
from config import ADMIN_IDS
from datetime import datetime

async def request_withdraw(update, context):
    user_id = update.effective_user.id
    args = context.args

    if len(args) < 2:
        await update.message.reply_text("❌ استخدم: /withdraw <المبلغ> <عنوان Binance>")
        return

    try:
        amount = float(args[0])
    except:
        await update.message.reply_text("❌ مبلغ غير صالح")
        return

    wallet = args[1]
    min_withdraw = 2.0

    c = get_conn().cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    balance = row[0] if row else 0

    if amount < min_withdraw:
        await update.message.reply_text(f"❌ الحد الأدنى للسحب: {min_withdraw}$")
        return

    if amount > balance:
        await update.message.reply_text("❌ رصيدك غير كافٍ")
        return

    # إنشاء طلب سحب
    c.execute("""
    INSERT INTO withdraws(user_id, amount, wallet, request_date)
    VALUES(?,?,?,?)
    """, (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # خصم المبلغ مؤقتاً
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    c.connection.commit()

    # إرسال إشعار للأدمن
    c.execute("SELECT username, join_date, referrals_count FROM users WHERE user_id=?", (user_id,))
    user_info = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (user_id,))
    links_count = c.fetchone()[0]
    
    c.execute("SELECT SUM(earned) FROM links WHERE user_id=?", (user_id,))
    total_from_links = c.fetchone()[0] or 0
    
    c.connection.close()

    admin_msg = f"""
📥 **طلب سحب جديد**
👤 المستخدم: {user_info[0]} (`{user_id}`)
💰 المبلغ: {amount}$
🏦 المحفظة: `{wallet}`
📅 تاريخ التسجيل: {user_info[1]}
🔗 عدد الروابط: {links_count}
👥 عدد المدعوين: {user_info[2]}
💵 أرباح الروابط: {total_from_links:.3f}$
    """

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_msg)
        except:
            pass

    await update.message.reply_text("✅ تم تقديم طلب السحب، سيتم مراجعته قريباً")
