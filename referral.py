from db import get_conn
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

def process_referral_commission(earned_amount, user_id):
    c = get_conn().cursor()
    
    # جلب معرف الشخص الذي دعا هذا المستخدم
    c.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    if row and row[0] != 0:
        referrer_id = row[0]
        commission = earned_amount * 0.10  # 10% للمُحيل
        
        # إضافة العمولة للمُحيل
        c.execute("UPDATE users SET balance=balance+?, total=total+? WHERE user_id=?",
                  (commission, commission, referrer_id))
    
    c.connection.commit()
    c.connection.close()
