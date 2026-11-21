# -*- coding: utf-8 -*-
"""
آنتی‌فلود: اگر یک کاربر طی ۱ دقیقه ۳۰ پیام بفرستد:
    - تخلف اول  -> پیام «مگه بازیچه دست تو‌ام؟» + مسدودی موقت ۳۰ دقیقه‌ای
    - تخلف دوم به بعد -> مسدودی دائم + گزارش به OWNER_ID با دکمه‌ی «رحمش کن»

⚠️ محدودیت واقعی API تلگرام: ربات هرگز نمی‌تواند پیام‌های یک کاربر را در چت
خصوصی پاک کند (فقط پیام‌های خودش را می‌تواند پاک کند، و پیام‌های دیگران را
فقط در گروه‌هایی که ادمین است). به همین دلیل، به‌جای «پاک کردن پیام کاربر»،
ربات از لحظه‌ی مسدودی به بعد کاملاً سکوت می‌کند — یعنی هیچ پاسخی نمی‌دهد و
هیچ دکمه‌ای کار نمی‌کند — تا آخرین پیام *ربات* در چت همان هشدار بماند.
"""
import threading
from collections import deque
from datetime import datetime

from base import database as db
from base.core import bot

_msg_times: dict = {}
_msg_times_lock = threading.Lock()

_FLOOD_WINDOW_SECONDS = 60
_FLOOD_THRESHOLD       = 30

# فازِ جدید: هر چقدر هم کاربر مسدود (موقت/دائم) باشه، این متن‌ها همیشه
# باید به هندلرِ اصلی‌شون برسن - چون تنها راهِ کاربرِ مسدودشده برای
# درخواستِ رفعِ مسدودیت همینه؛ اگه این یکی رو هم ساکت کنیم، کاربر هیچ
# راهی برای برگشتن نداره جز ساختن یه چتِ تازه.
_ALWAYS_ALLOWED_TEXTS = {'ارتباط با ادمین', '📞 ارتباط با ادمین'}


def _hit_threshold(uid: int) -> bool:
    now = datetime.utcnow()
    with _msg_times_lock:
        dq = _msg_times.setdefault(uid, deque())
        dq.append(now)
        while dq and (now - dq[0]).total_seconds() > _FLOOD_WINDOW_SECONDS:
            dq.popleft()
        return len(dq) >= _FLOOD_THRESHOLD


def is_currently_blocked(uid: int) -> bool:
    """فقط چک می‌کند، هیچ تغییری نمی‌دهد. برای استفاده در ابتدای هندلر پیام."""
    state = db.get_flood_state(uid)
    if not state:
        return False
    if state.get('permanently_blocked'):
        return True
    if state.get('blocked_until'):
        until = datetime.fromisoformat(state['blocked_until'])
        if datetime.utcnow() < until:
            return True
    return False


def check_and_handle(message) -> bool:
    """
    این تابع باید همان اول هندلر پیام خصوصی صدا زده شود.
    خروجی True یعنی «پردازش عادی پیام را متوقف کن» (کاربر مسدود است یا همین
    الان مسدود شد). خروجی False یعنی پیام کاملاً عادی است، ادامه بده.
    """
    uid  = message.from_user.id
    cid  = message.chat.id

    if (message.text or '').strip() in _ALWAYS_ALLOWED_TEXTS:
        return False

    if is_currently_blocked(uid):
        return True

    if not _hit_threshold(uid):
        return False

    # به آستانه‌ی ۳۰ پیام در ۱ دقیقه رسید
    state          = db.get_flood_state(uid)
    offense_before = (state or {}).get('offense_count', 0)

    if offense_before >= 1:
        _apply_permanent_block(uid, cid, message)
    else:
        bot.send_message(cid, 'مگه بازیچه دست تو ام؟')
        db.flood_temp_block(uid, minutes=30)
    return True


def _apply_permanent_block(uid: int, cid: int, message):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    zone_id = db.get_user_zone_id(uid)
    tmpl = db.get_zone_setting(zone_id, 'flood_block_msg', None) or (
        'شما به دلیل بازیچه گرفتن ربات توسط ربات مسدود شدید.\n'
        'با ادمین ربات پیام بدید تا از مسدودی خارج شوید.'
    )
    try:
        notice = bot.send_message(cid, tmpl)
        db.flood_permanent_block(uid, cid, notice.message_id)
    except Exception:
        db.flood_permanent_block(uid, cid, 0)

    try:
        owner_id = db.get_owner_id()
        if not owner_id:
            return
        fn = message.from_user.first_name or '(بدون نام)'
        un = f'@{message.from_user.username}' if message.from_user.username else '(ندارد)'
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('🙏 رحمش کن', callback_data=f'flood:forgive_ask:{uid}'))
        bot.send_message(
            owner_id,
            '🔴 <b>گزارش مسدودی کاربر توسط ربات</b>\n\n'
            'این بنده خدا ۳۰ تا پیام داده\n\n'
            f'اسمش: {fn}\nیوزرنیمش: {un}\nایدی عددیش: <code>{uid}</code>',
            parse_mode='HTML', reply_markup=kb,
        )
    except Exception:
        pass
