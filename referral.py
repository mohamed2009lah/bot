from db import get_conn
from points import points_system
import random
import string

def generate_ref_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def add_referral(new_user_id, referrer_id):
    c = get_conn().cursor()
    
    # تحديث عدد المدعوين
    c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?", (referrer_id,))
    c.connection.commit()
    c.connection.close()
    
    # إضافة نقاط للداعي
    try:
        points_system.add_referral_points(referrer_id)
    except:
        pass  # إذا لم يتم تهيئة نظام النقاط بعد

def process_referral_commission(earned_amount, user_id):
    """معالجة عمولة الإحالة 10%"""
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
