import random
from db import get_conn
from datetime import datetime

class AdsSystem:
    def __init__(self):
        self.ads = [
            {
                'id': 1,
                'text': "🎯 **عرض خاص!**\nاربح 50$ يومياً من اختصار الروابط\nسجل الآن: https://example.com",
                'type': 'text',
                'weight': 5  # احتمالية الظهور
            },
            {
                'id': 2,
                'text': "📢 **فرصة ذهبية!**\nتعلم الربح من الإنترنت مجاناً\nانضم الآن: https://example.com",
                'type': 'text',
                'weight': 3
            },
            {
                'id': 3,
                'text': "💎 **خصم 20%** على أول عملية شراء نقاط\nاستخدم الكود: WELCOME20",
                'type': 'text',
                'weight': 4
            },
            {
                'id': 4,
                'text': "🚀 **طور بوتك الخاص** مع أفضل المبرمجين\nللتواصل: @username",
                'type': 'text',
                'weight': 3
            },
            {
                'id': 5,
                'text': "📊 **إحصائيات مذهلة:**\nأكثر من 10,000 مستخدم يربحون يومياً\nانضم للربح الآن!",
                'type': 'text',
                'weight': 2
            },
        ]
        
        self.referral_message = (
            "🔗 **هل تريد استخدام هذه الخدمة مجاناً؟**\n\n"
            "👥 ادعُ صديقاً واحداً لتحصل على نقاط مجانية!\n"
            "كل صديق = نقاط إضافية للخدمات\n\n"
            "استخدم /invite للحصول على رابط الدعوة"
        )
    
    def init_tables(self):
        """تهيئة جداول الإعلانات"""
        c = get_conn().cursor()
        
        c.execute("""
        CREATE TABLE IF NOT EXISTS ad_views(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad_id INTEGER,
            service TEXT,
            viewed_at TEXT
        )
        """)
        
        c.connection.commit()
        c.connection.close()
    
    def get_random_ad(self):
        """الحصول على إعلان عشوائي"""
        total_weight = sum(ad['weight'] for ad in self.ads)
        r = random.uniform(0, total_weight)
        cumsum = 0
        
        for ad in self.ads:
            cumsum += ad['weight']
            if r <= cumsum:
                return ad
        
        return self.ads[0]
    
    def show_ad(self, user_id, service):
        """عرض إعلان قبل الخدمة"""
        # تسجيل المشاهدة
        ad = self.get_random_ad()
        
        c = get_conn().cursor()
        c.execute("INSERT INTO ad_views(user_id, ad_id, service, viewed_at) VALUES(?,?,?,?)",
                  (user_id, ad['id'], service, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.connection.commit()
        c.connection.close()
        
        return ad['text']
    
    def should_show_referral(self, user_id):
        """هل يجب عرض رسالة الدعوة؟"""
        c = get_conn().cursor()
        c.execute("SELECT referrals_count FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        c.connection.close()
        
        if not row or row[0] == 0:
            return True
        return False
    
    def get_ad_stats(self):
        """إحصائيات الإعلانات للأدمن"""
        c = get_conn().cursor()
        
        # إجمالي المشاهدات
        c.execute("SELECT COUNT(*) FROM ad_views")
        total_views = c.fetchone()[0]
        
        # المشاهدات حسب الإعلان
        c.execute("""
        SELECT ad_id, COUNT(*) as views 
        FROM ad_views 
        GROUP BY ad_id 
        ORDER BY views DESC
        """)
        ad_stats = c.fetchall()
        
        c.connection.close()
        return total_views, ad_stats
