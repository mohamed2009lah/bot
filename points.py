from db import get_conn
from datetime import datetime

class PointsSystem:
    def __init__(self):
        self.service_costs = {
            'ocr': 4,        # استخراج النص
            'download': 5,   # تحميل فيديو
            'speak': 3,      # تحويل نص إلى صوت
            'separate': 8,   # فصل الصوت
            'shorten': 1,    # اختصار رابط
        }
        
        self.referral_points = 5  # نقاط لكل دعوة
        self.daily_bonus = 2      # نقاط يومية
    
    def init_tables(self):
        """تهيئة جداول النقاط"""
        c = get_conn().cursor()
        
        c.execute("""
        CREATE TABLE IF NOT EXISTS points(
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            last_daily_bonus TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """)
        
        c.execute("""
        CREATE TABLE IF NOT EXISTS points_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,  -- earn, spend, buy, referral, admin_grant, daily
            description TEXT,
            created_at TEXT
        )
        """)
        
        c.execute("""
        CREATE TABLE IF NOT EXISTS points_pricing(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount INTEGER,  -- عدد النقاط
            price REAL,      -- السعر بالدولار
            active INTEGER DEFAULT 1
        )
        """)
        
        c.connection.commit()
        c.connection.close()
        
        # إضافة الأسعار الافتراضية إذا لم تكن موجودة
        self._init_default_pricing()
    
    def _init_default_pricing(self):
        """إضافة أسعار افتراضية"""
        c = get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM points_pricing")
        if c.fetchone()[0] == 0:
            prices = [
                (10, 0.50),
                (25, 1.00),
                (50, 1.80),
                (100, 3.00),
                (250, 6.50),
                (500, 10.00),
                (1000, 18.00),
            ]
            for amount, price in prices:
                c.execute("INSERT INTO points_pricing(amount, price) VALUES(?,?)", (amount, price))
            c.connection.commit()
        c.connection.close()
    
    def get_balance(self, user_id):
        """الحصول على رصيد النقاط"""
        c = get_conn().cursor()
        c.execute("SELECT balance FROM points WHERE user_id=?", (user_id,))
        row = c.fetchone()
        c.connection.close()
        return row[0] if row else 0
    
    def add_points(self, user_id, amount, trans_type, description):
        """إضافة نقاط"""
        c = get_conn().cursor()
        
        # تحديث أو إنشاء سجل النقاط
        c.execute("""
        INSERT INTO points(user_id, balance, total_earned) 
        VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET 
        balance = balance + ?,
        total_earned = total_earned + ?
        """, (user_id, amount, amount, amount, amount))
        
        # تسجيل المعاملة
        c.execute("""
        INSERT INTO points_transactions(user_id, amount, type, description, created_at)
        VALUES(?,?,?,?,?)
        """, (user_id, amount, trans_type, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        c.connection.commit()
        c.connection.close()
    
    def spend_points(self, user_id, amount, description):
        """خصم نقاط"""
        if self.get_balance(user_id) < amount:
            return False
        
        c = get_conn().cursor()
        c.execute("UPDATE points SET balance = balance - ?, total_spent = total_spent + ? WHERE user_id=?",
                  (amount, amount, user_id))
        
        c.execute("""
        INSERT INTO points_transactions(user_id, amount, type, description, created_at)
        VALUES(?,?,?,?,?)
        """, (user_id, -amount, 'spend', description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        c.connection.commit()
        c.connection.close()
        return True
    
    def get_service_cost(self, service):
        """تكلفة الخدمة"""
        return self.service_costs.get(service, 5)
    
    def add_referral_points(self, referrer_id):
        """إضافة نقاط الدعوة"""
        self.add_points(referrer_id, self.referral_points, 'referral', 'مكافأة دعوة صديق جديد')
    
    def claim_daily_bonus(self, user_id):
        """استلام المكافأة اليومية"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        c = get_conn().cursor()
        c.execute("SELECT last_daily_bonus FROM points WHERE user_id=?", (user_id,))
        row = c.fetchone()
        
        if row and row[0] == today:
            c.connection.close()
            return False, "لقد استلمت مكافأتك اليومية بالفعل"
        
        self.add_points(user_id, self.daily_bonus, 'daily', 'المكافأة اليومية')
        
        c.execute("UPDATE points SET last_daily_bonus=? WHERE user_id=?", (today, user_id))
        c.connection.commit()
        c.connection.close()
        
        return True, f"✅ تمت إضافة {self.daily_bonus} نقاط إلى رصيدك"
    
    def get_pricing_list(self):
        """قائمة أسعار النقاط"""
        c = get_conn().cursor()
        c.execute("SELECT amount, price FROM points_pricing WHERE active=1 ORDER BY amount")
        rows = c.fetchall()
        c.connection.close()
        return rows
    
    def buy_points(self, user_id, package_amount):
        """شراء نقاط"""
        c = get_conn().cursor()
        c.execute("SELECT price FROM points_pricing WHERE amount=? AND active=1", (package_amount,))
        row = c.fetchone()
        
        if not row:
            c.connection.close()
            return None, "❌ باقة النقاط غير متوفرة"
        
        price = row[0]
        c.connection.close()
        
        self.add_points(user_id, package_amount, 'buy', f'شراء {package_amount} نقطة')
        return price, None
    
    def get_user_stats(self, user_id):
        """إحصائيات نقاط المستخدم"""
        c = get_conn().cursor()
        c.execute("""
        SELECT balance, total_earned, total_spent 
        FROM points WHERE user_id=?
        """, (user_id,))
        row = c.fetchone()
        c.connection.close()
        
        if row:
            return {'balance': row[0], 'total_earned': row[1], 'total_spent': row[2]}
        return {'balance': 0, 'total_earned': 0, 'total_spent': 0}
    
    def admin_grant_points(self, admin_id, target_user_id, amount):
        """الأدمن يمنح نقاط"""
        self.add_points(target_user_id, amount, 'admin_grant', f'منحة من الأدمن {admin_id}')
        return True
    
    def get_transactions(self, user_id, limit=10):
        """سجل معاملات النقاط"""
        c = get_conn().cursor()
        c.execute("""
        SELECT amount, type, description, created_at 
        FROM points_transactions 
        WHERE user_id=? 
        ORDER BY id DESC 
        LIMIT ?
        """, (user_id, limit))
        rows = c.fetchall()
        c.connection.close()
        return rows
