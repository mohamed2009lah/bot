from db import get_conn
from config import ADMIN_IDS, MIN_WITHDRAW
from datetime import datetime

async def request_withdraw(update, context):
    user_id = update.effective_user.id
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            f"❌ استخدم: /withdraw <المبلغ> <عنوان Binance>\n\n📌 الحد الأدنى: {MIN_WITHDRAW}$"
        )
        return

    try:
        amount = float(args[0])
    except:
        await update.message.reply_text("❌ مبلغ غير صالح")
        return

    wallet = args[1]

    c = get_conn().cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    balance = row[0] if row else 0

    if amount < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ الحد الأدنى للسحب: {MIN_WITHDRAW}$")
        c.connection.close()
        return

    if amount > balance:
        await update.message.reply_text(f"❌ رصيدك غير كافٍ. رصيدك: {balance:.3f}$")
        c.connection.close()
        return

    c.execute("INSERT INTO withdraws(user_id, amount, wallet, request_date) VALUES(?,?,?,?)",
              (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    c.connection.commit()

    c.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
    username = c.fetchone()[0]
    
    try:
        from points import points_system
        points_balance = points_system.get_balance(user_id)
    except:
        points_balance = 0
    
    c.connection.close()

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"📥 طلب سحب جديد\n👤 {username} ({user_id})\n💰 {amount:.3f}$\n🏦 {wallet}\n⭐ النقاط: {points_balance}"
            )
        except:
            pass

    await update.message.reply_text(f"✅ تم تقديم طلب سحب {amount:.3f}$")
