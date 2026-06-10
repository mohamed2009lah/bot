import asyncio
from db import get_conn
from api import stats

async def update_earnings(bot):
    c = get_conn().cursor()

    c.execute("SELECT id,user_id,short,last FROM links")
    rows = c.fetchall()

    for i, uid, url, last in rows:

        earned = await stats(url)
        if not earned or earned <= last:
            continue

        delta = earned - last
        share = delta * 0.7

        c.execute("""
        UPDATE users SET balance=balance+?, total=total+?
        WHERE user_id=?
        """, (share, delta, uid))

        c.execute("UPDATE links SET last=? WHERE id=?", (earned, i))

    c.connection.commit()
    c.connection.close()
