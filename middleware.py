from points import PointsSystem
from ads import AdsSystem
from db import get_conn

points_system = PointsSystem()
ads_system = AdsSystem()

class Middleware:
    """نظام التحقق من النقاط وعرض الإعلانات قبل الخدمات"""
    
    def __init__(self):
        self.free_services = ['help', 'start', 'balance', 'referral', 'withdraw', 'buy_points']
    
    async def check_and_process(self, user_id, service, context):
        """
        التحقق من توفر النقاط وعرض الإعلان
        يعيد: (allowed, message, skip_ad)
        """
        
        # الخدمات المجانية لا تحتاج نقاط
        if service in self.free_services:
            return True, None, True
        
        # الحصول على تكلفة الخدمة
        cost = points_system.get_service_cost(service)
        balance = points_system.get_balance(user_id)
        
        # إذا المستخدم ليس لديه نقاط كافية
        if balance < cost:
            # عرض رسالة الدعوة إذا لم يدعُ أحداً
            if ads_system.should_show_referral(user_id):
                msg = ads_system.referral_message
                msg += f"\n\n⭐ تحتاج {cost} نقاط لهذه الخدمة\nرصيدك: {balance} نقطة"
                return False, msg, True
            
            msg = f"⭐ **رصيد نقاطك غير كافٍ**\n\n"
            msg += f"💰 تحتاج: {cost} نقطة\n"
            msg += f"📊 رصيدك: {balance} نقطة\n\n"
            msg += "🛒 لشراء نقاط: /buy_points"
            return False, msg, True
        
        # خصم النقاط
        success = points_system.spend_points(user_id, cost, f'استخدام خدمة {service}')
        
        if not success:
            return False, "❌ حدث خطأ في خصم النقاط", True
        
        # عرض إعلان
        ad_text = ads_system.show_ad(user_id, service)
        
        points_after = points_system.get_balance(user_id)
        msg = f"📢 **إعلان ممول:**\n\n{ad_text}\n\n"
        msg += f"✅ تم خصم {cost} نقطة | رصيدك: {points_after} نقطة"
        
        return True, msg, False
    
    def get_service_cost_info(self):
        """معلومات تكاليف الخدمات"""
        costs = points_system.service_costs
        msg = "📊 **تكاليف الخدمات (بالنقاط):**\n\n"
        msg += f"🔗 اختصار رابط: {costs['shorten']} نقطة\n"
        msg += f"📸 استخراج نص: {costs['ocr']} نقاط\n"
        msg += f"📥 تحميل فيديو: {costs['download']} نقاط\n"
        msg += f"🎙️ تحويل نص لصوت: {costs['speak']} نقاط\n"
        msg += f"🎵 فصل الصوت: {costs['separate']} نقاط\n\n"
        msg += "💡 ادعُ أصدقاءك لتحصل على 5 نقاط لكل صديق!\n"
        msg += "🛒 أو اشترِ نقاط: /buy_points"
        return msg
