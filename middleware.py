from points import points_system
from ads import ads_system

class Middleware:
    def __init__(self):
        self.free_services = ['help','start','balance','referral','withdraw','buy_points','points','daily','invite']

    async def check_and_process(self, user_id, service, context):
        if service in self.free_services:
            return True, None, True
        cost = points_system.get_service_cost(service)
        bal = points_system.get_balance(user_id)
        if bal < cost:
            if ads_system.should_show_referral(user_id):
                msg = ads_system.referral_message + f"\n\n⭐ تحتاج {cost} نقطة | رصيدك: {bal}"
                return False, msg, True
            return False, f"⭐ رصيدك غير كافٍ\nتحتاج {cost} نقطة\nرصيدك {bal}\n🛒 /buy_points", True
        if not points_system.spend_points(user_id, cost, f'استخدام {service}'):
            return False, "❌ خطأ في الخصم", True
        ad = ads_system.show_ad(user_id, service)
        pts = points_system.get_balance(user_id)
        msg = f"📢 **إعلان:**\n\n{ad}\n\n✅ خصم {cost} نقطة | رصيدك: {pts}"
        return True, msg, False

    def get_service_cost_info(self):
        c = points_system.service_costs
        msg = "📊 تكاليف الخدمات:\n"
        msg += f"🔗 اختصار: {c['shorten']} نقطة\n"
        msg += f"📸 OCR: {c['ocr']} نقاط\n"
        msg += f"📥 تحميل: {c['download']} نقاط\n"
        msg += f"🎙️ TTS: {c['speak']} نقاط\n"
        msg += f"🎵 فصل الصوت: {c['separate']} نقاط\n"
        msg += "\n💡 ادعُ أصدقاء (5 نقاط) أو /buy_points"
        return msg

middleware = Middleware()