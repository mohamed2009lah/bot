from points import points_system
from ads import ads_system

class Middleware:
    def __init__(self):
        self.free_services = ['help', 'start', 'balance', 'referral', 'withdraw', 'buy_points', 'points', 'daily', 'invite']
    
    async def check_and_process(self, user_id, service, context):
        if service in self.free_services:
            return True, None, True
        
        cost = points_system.get_service_cost(service)
        balance = points_system.get_balance(user_id)
        
        if balance < cost:
            if ads_system.should_show_referral(user_id):
                msg = ads_system.referral_message
                msg += f"\n\n⭐ تحتاج {cost} نقاط لهذه الخدمة\nرصيدك: {balance} نقطة"
                return False, msg, True
            
            msg = f"⭐ **رصيد نقاطك غير كافٍ**\n\n💰 تحتاج: {cost} نقطة\n📊 رصيدك: {balance} نقطة\n\n🛒 لشراء نقاط: /buy_points"
            return False, msg, True
        
        success = points_system.spend_points(user_id, cost, f'استخدام خدمة {service}')
        if not success:
            return False, "❌ حدث خطأ في خصم النقاط", True
        
        ad_text = ads_system.show_ad(user_id, service)
        points_after = points_system.get_balance(user_id)
        msg = f"📢 **إعلان ممول:**\n\n{ad_text}\n\n✅ تم خصم {cost} نقطة | رصيدك: {points_after} نقطة"
        
        return True, msg, False
    
    def get_service_cost_info(self):
        costs = points_system.service_costs
        msg = "📊 **تكاليف الخدمات (بالنقاط):**\n\n"
        msg += f"🔗 اختصار رابط: {costs['shorten']} نقطة\n"
        msg += f"📸 استخراج نص: {costs['ocr']} نقاط\n"
        msg += f"📥 تحميل فيديو: {costs['download']} نقاط\n"
        msg += f"🎙️ تحويل نص لصوت: {costs['speak']} نقاط\n"
        msg += f"🎵 فصل الصوت: {costs['separate']} نقاط\n\n"
        msg += "💡 ادعُ أصدقاءك لتحصل على 5 نقاط لكل صديق يشاهد الإعلان!\n🛒 أو اشترِ نقاط: /buy_points"
        return msg


middleware = Middleware()
