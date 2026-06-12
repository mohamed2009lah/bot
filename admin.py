import asyncio
from db import get_conn

async def broadcast(bot, message: str):
    """إرسال رسالة لجميع المستخدمين"""
    c = get_conn().cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    c.connection.close()

    ok, fail = 0, 0

    for i, u in enumerate(users):
        try:
            await bot.send_message(u[0], f"📢 {message}", parse_mode="HTML")
            ok += 1
            # تأخير بسيط لتجنب حظر تيليجرام
            if i % 25 == 0:
                await asyncio.sleep(1)
        except:
            fail += 1

    return ok, fail

async def broadcast_to_active(bot, message: str, days=7):
    """إرسال رسالة للمستخدمين النشطين فقط"""
    from datetime import datetime, timedelta
    
    c = get_conn().cursor()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    c.execute("""
    SELECT DISTINCT u.user_id 
    FROM users u 
    JOIN links l ON u.user_id = l.user_id 
    WHERE l.created_at >= ?
    """, (since,))
    
    users = c.fetchall()
    c.connection.close()

    ok, fail = 0, 0
    for i, u in enumerate(users):
        try:
            await bot.send_message(u[0], f"📢 {message}", parse_mode="HTML")
            ok += 1
            if i % 25 == 0:
                await asyncio.sleep(1)
        except:
            fail += 1

    return ok, fail
