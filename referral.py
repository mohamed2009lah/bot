from db import get_conn
from datetime import datetime
import random
import string

def generate_ref_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def add_referral(new_user_id, referrer_id):
    """تسجيل دعوة جديدة (بدون نقاط - النقاط بعد مشاهدة الإعلان)"""
    c = get_conn().cursor()
    
    # تحديث عدد المدعوين
    c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?", (referrer_id,))
    
    # تسجيل في جدول التتبع
    c.execute("""
    INSERT INTO referral_tracking(referrer_id, new_user_id, created_at)
    VALUES(?,?,?)
    """, (referrer_id, new_user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    c.connection.commit()
    c.connection.close()

def get_referral_stats(user_id):
    """إحصائيات الدعوات لمستخدم"""
    c = get_conn().cursor()
    
    # إجمالي المدعوين
    c.execute("SELECT referrals_count, referrals_watched_ads FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    total_invited = row[0] if row else 0
    watched_ads = row[1] if row else 0
    
    # المعلقين (لم يشاهدوا الإعلان بعد)
    pending = total_invited - watched_ads
    
    c.connection.close()
    return {
        'total_invited': total_invited,
        'watched_ads': watched_ads,
        'pending': pending
    }

def process_referral_commission(earned_amount, user_id):
    """معالجة عمولة الإحالة 10% من الأرباح"""
    c = get_conn().cursor()
    c.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row and row[0] != 0:
        referrer_id = row[0]
        commission = earned_amount * 0.10
        c.execute("UPDATE users SET balance=balance+?, total=total+? WHERE user_id=?",
                  (commission, commission, referrer_id))
    c.connection.commit()
    c.connection.close()
