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
        referred_by INTEGER DEFAULT 0,
        ref_code TEXT UNIQUE,
        join_date TEXT,
        referrals_count INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS links(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        original_url TEXT,
        short TEXT,
        earned REAL DEFAULT 0,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS withdraws(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        wallet TEXT,
        status TEXT DEFAULT 'pending',
        request_date TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS support_tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        reply TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT
    )
    """)

    c.connection.commit()
    c.connection.close()
