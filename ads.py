import random
from db import get_conn
from datetime import datetime

class AdsSystem:
    def __init__(self):
        self.ads = [
            {'id': 1, 'text': "📢 **إعلان ممول**\n\n🎯 **عرض خاص!**\nاربح 50$ يومياً من اختصار الروابط\nسجل الآن: https://example.com", 'weight': 5},
            {'id': 2, 'text': "📢 **إعلان ممول**\n\n📢 **فرصة ذهبية!**\nتعلم الربح من الإنترنت مجاناً\nانضم الآن: https://example.com", 'weight': 3},
            {'id': 3, 'text': "📢 **إعلان ممول**\n\n💎 **خصم 20%** على أول عملية شراء نقاط\nاستخدم الكود: WELCOME20", 'weight': 4},
            {'id': 4, 'text': "📢 **إعلان ممول**\n\n🚀 **طور بوتك الخاص** مع أفضل المبرمجين\nللتواصل: @DevSupport", 'weight': 3},
            {'id': 5, 'text': "📢 **إعلان ممول**\n\n📊 **إحصائيات مذهلة:**\nأكثر من 10,000 مستخدم يربحون يومياً\nانضم للربح الآن!", 'weight': 2},
        ]
        self.referral_message = (
            "🔗 **هل تريد استخدام هذه الخدمة مجاناً؟**\n\n"
            "👥 ادعُ صديقاً واحداً لتحصل على نقاط مجانية!\n"
            "⭐ كل صديق يشاهد الإعلان = 5 نقاط للخدمات\n\n"
            "استخدم /invite للحصول على رابط الدعوة"
        )
    
    def init_tables(self):
        pass
    
    def show_ad(self, user_id, service):
        """عرض إعلان وتسجيله"""
        ad = self._get_random_ad()
        c = get_conn().cursor()
        c.execute("INSERT INTO ad_views(user_id, ad_id, service, viewed_at) VALUES(?,?,?,?)",
                  (user_id, ad['id'], service, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.connection.commit()
        c.connection.close()
        return ad['text']
    
    def show_referral_ad(self, new_user_id, referrer_id):
        """عرض إعلان للمستخدم الجديد وتحديث تتبع الدعوة"""
        ad = self._get_random_ad()
        c = get_conn().cursor()
        c.execute("INSERT INTO ad_views(user_id, ad_id, service, viewed_at) VALUES(?,?,?,?)",
                  (new_user_id, ad['id'], 'referral', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # تحديث تتبع الدعوة - تمت مشاهدة الإعلان
        c.execute("""
        UPDATE referral_tracking 
        SET ad_watched = 1 
        WHERE new_user_id = ? AND referrer_id = ? AND ad_watched = 0
        """, (new_user_id, referrer_id))
        
        # إذا تم تحديث صف، نعطي النقاط للداعي
        if c.rowcount > 0:
            c.execute("UPDATE referral_tracking SET points_awarded = 1 WHERE new_user_id = ? AND referrer_id = ?",
                      (new_user_id, referrer_id))
            c.execute("UPDATE users SET referrals_watched_ads = referrals_watched_ads + 1 WHERE user_id = ?",
                      (referrer_id,))
            
            # إعطاء النقاط للداعي
            from points import points_system
            points_system.add_referral_points(referrer_id)
        
        c.connection.commit()
        c.connection.close()
        return ad['text']
    
    def _get_random_ad(self):
        total_weight = sum(ad['weight'] for ad in self.ads)
        r = random.uniform(0, total_weight)
        cumsum = 0
        for ad in self.ads:
            cumsum += ad['weight']
            if r <= cumsum:
                return ad
        return self.ads[0]
    
    def should_show_referral(self, user_id):
        c = get_conn().cursor()
        c.execute("SELECT referrals_count FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        c.connection.close()
        return not row or row[0] == 0
    
    def get_daily_ad_stats(self):
        """إحصائيات إعلانات اليوم"""
        today = datetime.now().strftime("%Y-%m-%d")
        c = get_conn().cursor()
        
        # مشاهدات اليوم
        c.execute("SELECT COUNT(*) FROM ad_views WHERE viewed_at >= ?", (today,))
        today_views = c.fetchone()[0]
        
        # مشاهدات اليوم حسب الإعلان
        c.execute("""
        SELECT ad_id, COUNT(*) as views 
        FROM ad_views 
        WHERE viewed_at >= ? 
        GROUP BY ad_id 
        ORDER BY views DESC
        """, (today,))
        today_by_ad = c.fetchall()
        
        # مشاهدات اليوم حسب الخدمة
        c.execute("""
        SELECT service, COUNT(*) as views 
        FROM ad_views 
        WHERE viewed_at >= ? 
        GROUP BY service 
        ORDER BY views DESC
        """, (today,))
        today_by_service = c.fetchall()
        
        c.connection.close()
        return today_views, today_by_ad, today_by_service
    
    def get_total_ad_stats(self):
        """إحصائيات الإعلانات الكلية"""
        c = get_conn().cursor()
        
        # إجمالي المشاهدات
        c.execute("SELECT COUNT(*) FROM ad_views")
        total_views = c.fetchone()[0]
        
        # إجمالي المشاهدات حسب الإعلان
        c.execute("""
        SELECT ad_id, COUNT(*) as views 
        FROM ad_views 
        GROUP BY ad_id 
        ORDER BY views DESC
        """)
        total_by_ad = c.fetchall()
        
        # إجمالي المشاهدات حسب الخدمة
        c.execute("""
        SELECT service, COUNT(*) as views 
        FROM ad_views 
        GROUP BY service 
        ORDER BY views DESC
        """)
        total_by_service = c.fetchall()
        
        # إحصائيات الإحالات
        c.execute("SELECT COUNT(*) FROM referral_tracking")
        total_referrals = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE ad_watched = 1")
        watched_referrals = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE points_awarded = 1")
        awarded_referrals = c.fetchone()[0]
        
        c.connection.close()
        return {
            'total_views': total_views,
            'total_by_ad': total_by_ad,
            'total_by_service': total_by_service,
            'total_referrals': total_referrals,
            'watched_referrals': watched_referrals,
            'awarded_referrals': awarded_referrals,
        }
    
    def add_manual_ad(self, text, weight=3):
        new_id = max([ad['id'] for ad in self.ads], default=0) + 1
        self.ads.append({'id': new_id, 'text': text, 'weight': weight})
        return new_id
    
    def remove_manual_ad(self, ad_id):
        self.ads = [ad for ad in self.ads if ad['id'] != ad_id]
        return True
    
    def get_all_manual_ads(self):
        return self.ads


ads_system = AdsSystem()
