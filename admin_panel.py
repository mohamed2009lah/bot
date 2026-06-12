from db import get_conn
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

class AdminPanel:
    def __init__(self):
        pass
    
    async def show_main_panel(self, update: Update):
        """عرض اللوحة الرئيسية للأدمن"""
        keyboard = [
            [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
            [InlineKeyboardButton("⭐ إدارة النقاط", callback_data="admin_points")],
            [InlineKeyboardButton("📢 إرسال إعلان للجميع", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📈 إحصائيات الإعلانات", callback_data="admin_adstats")],
            [InlineKeyboardButton("💳 طلبات السحب", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("👤 إعطاء نقاط لمستخدم", callback_data="admin_grant")],
        ]
        
        await update.message.reply_text(
            "🔐 **لوحة تحكم الأدمن**\nاختر العملية:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def get_bot_stats(self):
        """إحصائيات البوت الشاملة"""
        c = get_conn().cursor()
        
        # إجمالي المستخدمين
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        # مستخدمي هذا الشهر
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (first_day,))
        monthly_users = c.fetchone()[0]
        
        # المستخدمين النشطين اليوم
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(DISTINCT user_id) FROM links WHERE created_at >= ?", (today,))
        active_today = c.fetchone()[0]
        
        # مستخدمين آخر 24 ساعة
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT COUNT(DISTINCT user_id) FROM links WHERE created_at >= ?", (yesterday,))
        active_24h = c.fetchone()[0]
        
        # إجمالي الروابط
        c.execute("SELECT COUNT(*) FROM links")
        total_links = c.fetchone()[0]
        
        # إجمالي الأرباح
        c.execute("SELECT SUM(total) FROM users")
        total_earnings = c.fetchone()[0] or 0
        
        # إجمالي النقاط
        c.execute("SELECT SUM(balance) FROM points")
        total_points = c.fetchone()[0] or 0
        
        # إجمالي السحوبات
        c.execute("SELECT COUNT(*), SUM(amount) FROM withdraws")
        wd_count, wd_total = c.fetchone()
        
        c.connection.close()
        
        return {
            'total_users': total_users,
            'monthly_users': monthly_users,
            'active_today': active_today,
            'active_24h': active_24h,
            'total_links': total_links,
            'total_earnings': total_earnings or 0,
            'total_points': total_points,
            'wd_count': wd_count or 0,
            'wd_total': wd_total or 0,
        }
    
    def get_users_list(self, page=1, per_page=10):
        """قائمة المستخدمين"""
        c = get_conn().cursor()
        offset = (page - 1) * per_page
        
        c.execute("""
        SELECT user_id, username, balance, total, referrals_count, join_date 
        FROM users 
        ORDER BY user_id DESC 
        LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        users = c.fetchall()
        
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        
        c.connection.close()
        return users, total
    
    def search_user(self, query):
        """البحث عن مستخدم"""
        c = get_conn().cursor()
        
        c.execute("""
        SELECT user_id, username, balance, total, referrals_count, join_date 
        FROM users 
        WHERE user_id=? OR username LIKE ?
        """, (query if query.isdigit() else 0, f"%{query}%"))
        
        users = c.fetchall()
        c.connection.close()
        return users
    
    def get_points_management(self):
        """إدارة النقاط"""
        c = get_conn().cursor()
        
        # أعلى 10 مستخدمين نقاطاً
        c.execute("""
        SELECT u.user_id, u.username, p.balance, p.total_earned, p.total_spent
        FROM points p
        JOIN users u ON p.user_id = u.user_id
        ORDER BY p.balance DESC
        LIMIT 10
        """)
        top_users = c.fetchall()
        
        # إحصائيات النقاط
        c.execute("SELECT SUM(balance) FROM points")
        total_balance = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_earned) FROM points")
        total_earned = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_spent) FROM points")
        total_spent = c.fetchone()[0] or 0
        
        # نقاط البيع اليوم
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("""
        SELECT COUNT(*), SUM(amount) 
        FROM points_transactions 
        WHERE type='buy' AND created_at >= ?
        """, (today,))
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
