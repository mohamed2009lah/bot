import sqlite3

DB = "bot.db"

def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init():
    c = get_conn().cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        total REAL DEFAULT 0,
        ref TEXT,
        referred_by INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS links(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        short TEXT,
        last REAL DEFAULT 0
    )
    """)

    c.connection.commit()
    c.connection.close()
