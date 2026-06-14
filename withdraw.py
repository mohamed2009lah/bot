from db import get_conn
from config import ADMIN_IDS, MIN_WITHDRAW
from datetime import datetime

async def request_withdraw(update, context):
    user_id = update.effective_user.id
    args = context.args
    if len(args)<2:
        await update.message.reply_text(f"❌ /withdraw <المبلغ> <عنوان Binance>\nالحد الأدنى: {MIN_WITHDRAW}$")
        return
    try: amount = float(args[0])
    except: await update.message.reply_text("❌ مبلغ غير صالح"); return
    wallet = args[1]
    c = get_conn().cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?",(user_id,))
    balance = c.fetchone()[0] if c.fetchone() else 0
    if amount<MIN_WITHDRAW: await update.message.reply_text(f"❌ الحد الأدنى {MIN_WITHDRAW}$"); c.connection.close(); return
    if amount>balance: await update.message.reply_text("❌ رصيد غير كاف"); c.connection.close(); return
    c.execute("INSERT INTO withdraws(user_id,amount,wallet,request_date) VALUES(?,?,?,?)",
              (user_id,amount,wallet,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?",(amount,user_id))
    c.connection.commit()
    c.execute("SELECT username FROM users WHERE user_id=?",(user_id,))
    username = c.fetchone()[0]
    try:
        from points import points_system
        pts = points_system.get_balance(user_id)
    except: pts=0
    c.connection.close()
    for a in ADMIN_IDS:
        try: await context.bot.send_message(a, f"📥 طلب سحب\n👤 {username} ({user_id})\n💰 {amount:.3f}$\n🏦 {wallet}\n⭐ {pts}")
        except: pass
    await update.message.reply_text(f"✅ تم تقديم طلب سحب {amount:.3f}$")