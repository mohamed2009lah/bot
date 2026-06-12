from db import get_conn
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from ads import ads_system

class AdminPanel:
    async def show_main_panel(self, update: Update):
        keyboard = [
            [InlineKeyboardButton("📊 إحصائيات شاملة", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 إحصائيات الإعلانات", callback_data="admin_adstats")],
            [InlineKeyboardButton("👥 إحصائيات الدعوات", callback_data="admin_referrals")],
            [InlineKeyboardButton("⭐ إدارة النقاط", callback_data="admin_points")],
            [InlineKeyboardButton("💳 طلبات السحب", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📢 إرسال للجميع", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👤 منح نقاط", callback_data="admin_grant")],
            [InlineKeyboardButton("📝 إدارة الإعلانات", callback_data="admin_manageads")],
        ]
        await update.message.reply_text(
            "🔐 **لوحة تحكم الأدمن المتطورة**\nاختر العملية:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def get_full_stats(self):
        """إحصائيات شاملة"""
        c = get_conn().cursor()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # المستخدمين
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (month_start,))
        monthly_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM links WHERE created_at >= ?", (today,))
        active_today = c.fetchone()[0]
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM links WHERE created_at >= ?", (yesterday,))
        active_24h = c.fetchone()[0]
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM ad_views WHERE viewed_at >= ?", (today,))
        active_ads_today = c.fetchone()[0]
        
        # الروابط
        c.execute("SELECT COUNT(*) FROM links")
        total_links = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM links WHERE created_at >= ?", (today,))
        today_links = c.fetchone()[0]
        
        # الأرباح
        c.execute("SELECT SUM(total) FROM users")
        total_earnings = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(balance) FROM users")
        total_balance = c.fetchone()[0] or 0
        
        # النقاط
        c.execute("SELECT SUM(balance) FROM points")
        total_points = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*), SUM(amount) FROM points_transactions WHERE type='buy' AND created_at >= ?", (today,))
        buys_count, buys_total = c.fetchone()
        
        # السحوبات
        c.execute("SELECT COUNT(*) FROM withdraws WHERE status='pending'")
        pending_wd = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*), SUM(amount) FROM withdraws")
        wd_count, wd_total = c.fetchone()
        
        c.connection.close()
        
        return {
            'total_users': total_users,
            'monthly_users': monthly_users,
            'active_today': active_today,
            'active_24h': active_24h,
            'active_ads_today': active_ads_today,
            'total_links': total_links,
            'today_links': today_links,
            'total_earnings': total_earnings or 0,
            'total_balance': total_balance or 0,
            'total_points': total_points,
            'buys_count': buys_count or 0,
            'buys_total': buys_total or 0,
            'pending_wd': pending_wd,
            'wd_count': wd_count or 0,
            'wd_total': wd_total or 0,
        }
    
    def get_points_management(self):
        """إدارة النقاط"""
        c = get_conn().cursor()
        
        c.execute("""
        SELECT u.user_id, u.username, p.balance, p.total_earned, p.total_spent
        FROM points p JOIN users u ON p.user_id = u.user_id
        ORDER BY p.balance DESC LIMIT 10
        """)
        top_users = c.fetchall()
        
        c.execute("SELECT SUM(balance) FROM points")
        total_balance = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_earned) FROM points")
        total_earned = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_spent) FROM points")
        total_spent = c.fetchone()[0] or 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*), SUM(amount) FROM points_transactions WHERE type='buy' AND created_at >= ?", (today,))
        buys_today = c.fetchone()
        
        c.connection.close()
        
        return {
            'top_users': top_users,
            'total_balance': total_balance,
            'total_earned': total_earned,
            'total_spent': total_spent,
            'buys_count': buys_today[0] or 0,
            'buys_total': buys_today[1] or 0,
        }
    
    def get_referral_stats(self):
        """إحصائيات الدعوات"""
        c = get_conn().cursor()
        
        # إجمالي الدعوات
        c.execute("SELECT COUNT(*) FROM referral_tracking")
        total_referrals = c.fetchone()[0]
        
        # الدعوات التي شاهدت الإعلان
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE ad_watched = 1")
        watched_referrals = c.fetchone()[0]
        
        # الدعوات التي حصلت على نقاط
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE points_awarded = 1")
        awarded_referrals = c.fetchone()[0]
        
        # الدعوات المعلقة
        pending_referrals = total_referrals - watched_referrals
        
        # أفضل الداعين
        c.execute("""
        SELECT u.user_id, u.username, u.referrals_count, u.referrals_watched_ads,
               (u.referrals_count - u.referrals_watched_ads) as pending
        FROM users u
        WHERE u.referrals_count > 0
        ORDER BY u.referrals_watched_ads DESC
        LIMIT 10
        """)
        top_referrers = c.fetchall()
        
        c.connection.close()
        
        return {
            'total_referrals': total_referrals,
            'watched_referrals': watched_referrals,
            'awarded_referrals': awarded_referrals,
            'pending_referrals': pending_referrals,
            'top_referrers': top_referrers,
        }


admin_panel = AdminPanel()
