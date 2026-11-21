# -*- coding: utf-8 -*-
"""
هسته‌ی ربات: نمونه‌ی bot، قفل تک‌نمونه‌ای، مدیریت state، دکوریتور محافظ خطا،
توابع مجوز، و ساختارهای درون‌حافظه‌ای مشترک بین کل ماژول‌ها.
هر ماژول دیگری که به شیء `bot` یا این کمک‌تابع‌ها نیاز دارد، از اینجا ایمپورت
می‌کند.
"""
import os
import sys
import time
import functools
import logging
import threading
import html as _html
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import telebot

from base import database as db
from base.config import BOT_TOKEN


# ─────────────────────────────────────────────────────────────────────────────
# قفل تک‌نمونه‌ای (Single Instance Lock) — روی لینوکس و ویندوز هر دو کار می‌کند
# ─────────────────────────────────────────────────────────────────────────────
# اگه یه نسخه از همین ربات (همین توکن) از قبل در حال اجرا باشه (چه دستی، چه با
# systemd که تازه ری‌استارت شده و نسخه‌ی قدیمی هنوز کاملاً نمرده)، این قفل
# جلوی اجرای نسخه‌ی دوم رو می‌گیره تا هیچ‌وقت دو تا polling همزمان روی یه توکن
# نداشته باشیم (که باعث دوبار ارسال شدن هر پیام می‌شد).
#
# نام فایل قفل بر اساس هش خودِ BOT_TOKEN ساخته می‌شود، نه یک اسم ثابت — چون
# اگر چند ربات (با توکن‌های متفاوت) روی همین سرور در پوشه‌های جدا اجرا شوند،
# نباید سر یک فایل قفل مشترک با هم تصادم کنند؛ هرکدام باید فقط جلوی «نسخه‌ی
# دوم خودش» را بگیرد.
import hashlib
_TOKEN_HASH     = hashlib.md5(BOT_TOKEN.encode()).hexdigest()[:12]
_LOCK_FILE_PATH = os.path.join(
    os.environ.get('TEMP') or os.environ.get('TMPDIR') or '/tmp',
    f'telegram_bot_{_TOKEN_HASH}.lock'
)
_lock_file_handle = open(_LOCK_FILE_PATH, 'w')

def _acquire_single_instance_lock():
    try:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        print(
            '❌ یک نسخه‌ی دیگر از همین ربات (همین توکن) از قبل در حال اجراست (قفل: %s).\n'
            'برای جلوگیری از ارسال دوبل پیام‌ها، این نسخه بسته می‌شود.\n'
            'اگر مطمئنی نسخه‌ی دیگری از همین ربات اجرا نیست، فایل قفل را دستی حذف کن و دوباره اجرا کن.'
            % _LOCK_FILE_PATH
        )
        sys.exit(1)

_acquire_single_instance_lock()


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
# نکته‌ی مهم: قبلاً اینجا یه کپی‌ی هاردکد از BOT_TOKEN/OWNER_ID بود که مقدارش
# مستقل از config.py بود - یعنی اگه توی config.py توکن رو عوض می‌کردی، ربات
# بازم مخفیانه از همین مقدار قدیمی استفاده می‌کرد! اون کپی حذف شد؛ الان فقط
# همون BOT_TOKEN بالا (ایمپورت‌شده از config.py) استفاده می‌شه، و OWNER_ID هم
# دیگه یه عدد ثابت نیست - با db.get_owner_id() به‌صورت پویا خونده می‌شه (چون
# با یوزرنیم مالک، خودکار resolve و توی دیتابیس ذخیره می‌شه، نه توی کد).

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

class _TelebotExceptionHandler(telebot.ExceptionHandler):
    """
    لایه‌ی محافظ نهایی: اگه خطایی حتی قبل از رسیدن به دکوریتور _safe_handler
    (مثلاً داخل خودِ کتابخونه‌ی pyTelegramBotAPI موقع دیسپچ کردن آپدیت) رخ بده،
    اینجا گرفته می‌شه و به‌جای گم شدن بی‌صدا، برای OWNER_ID گزارش می‌شه.
    """
    def handle(self, exception):
        log.error('Unhandled telebot exception: %s', exception, exc_info=True)
        try:
            report_error('Telebot internal', exception)
        except Exception:
            pass
        return True

bot = telebot.TeleBot(
    BOT_TOKEN, parse_mode=None, exception_handler=_TelebotExceptionHandler(),
    # فازِ ادامه: پیش‌فرضِ خودِ pyTelegramBotAPI برایِ num_threads فقط ۲ه؛
    # یعنی اگه یه پیام (مثلاً به‌خاطرِ ریتراییِ شبکه تو _safe_handler) چند
    # ثانیه طول بکشه، فقط همون یه ترد بلاک می‌شه ولی با ۲ تا کلاً نصفِ
    # ظرفیت رو گرفته - این خودش بزرگ‌ترین دلیلِ لگ‌کردنِ بات با چند
    # کاربر/گروهِ هم‌زمان بود. ۱۶ به‌اندازه‌ی کافی حاشیه می‌ده بدونِ
    # مصرفِ حافظه‌ی زیاد.
    threaded=True, num_threads=16,
)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory structures
# ─────────────────────────────────────────────────────────────────────────────
_states: dict      = {}
_states_lock       = threading.Lock()

_text_cache: dict  = {}
_text_cache_keys   = deque()
_MAX_CACHE_SIZE    = 500
_cache_seq: int    = 0
_cache_lock        = threading.Lock()

_last_activity: dict = {}
_last_activity_lock  = threading.Lock()

def _update_activity(uid: int):
    with _last_activity_lock:
        _last_activity[uid] = datetime.utcnow()

# ردیابی این‌که هر کاربر الان توی کدوم پنل Reply Keyboard هست (اصلی/توییتر/
# اینستاگرام) + آیدی آخرین پیام پنلی که برایش فرستاده شده — برای سوییچ تمیز
# بین پنل‌ها (ارسال پیام جدید، بعد حذف پیام قبلی).
_user_panel: dict = {}
_user_panel_lock  = threading.Lock()

def _get_user_panel(uid: int) -> str:
    with _user_panel_lock:
        return _user_panel.get(uid, {}).get('panel', 'main')

def _switch_panel(uid: int, cid: int, panel: str, text: str, kb, parse_mode=None, user_msg_id: int = None):
    """
    اول پیام جدید (با متن و دکمه‌های پنل مقصد) فرستاده می‌شود، و فقط بعد از
    ارسال موفق، پیام پنلی قبلی (اگر بود) حذف می‌شود — تا لحظه‌ای خالی از پیام/
    دکمه برای کاربر رخ ندهد. اگر user_msg_id داده شود (پیامی که خودِ کاربر با
    زدن دکمه فرستاده)، آن هم پاک می‌شود تا چت تمیز بماند.
    """
    new_msg = bot.send_message(cid, text, reply_markup=kb, parse_mode=parse_mode)
    with _user_panel_lock:
        old = _user_panel.get(uid, {})
        old_msg_id = old.get('msg_id')
        _user_panel[uid] = {'panel': panel, 'msg_id': new_msg.message_id}
    if old_msg_id:
        try:
            bot.delete_message(cid, old_msg_id)
        except Exception:
            pass
    if user_msg_id:
        try:
            bot.delete_message(cid, user_msg_id)
        except Exception:
            pass

def _cache_text(content: str) -> int:
    global _cache_seq
    with _cache_lock:
        _cache_seq += 1
        cid = _cache_seq
        _text_cache[cid] = content
        _text_cache_keys.append(cid)
        if len(_text_cache_keys) > _MAX_CACHE_SIZE:
            oldest = _text_cache_keys.popleft()
            _text_cache.pop(oldest, None)
    return cid

# ─────────────────────────────────────────────────────────────────────────────
# States
# ─────────────────────────────────────────────────────────────────────────────
S_WAIT_GROUP_HASHTAG  = 'wait_group_hashtag'
S_WAIT_GROUP_CONTENT  = 'wait_group_content'
S_WAIT_GROUP_REEL_CONTENT  = 'wait_group_reel_content'
S_WAIT_GROUP_STORY_CONTENT = 'wait_group_story_content'
S_WAIT_BROADCAST      = 'wait_broadcast'
S_WAIT_ADMIN_ID       = 'wait_admin_id'
S_WAIT_BOT_ADMIN_ID   = 'wait_bot_admin_id'
S_WAIT_LIMIT_HOURS    = 'wait_limit_hours'
S_WAIT_LIMIT_TEXTS    = 'wait_limit_texts'
S_WAIT_LIMIT_REEL_COUNT  = 'wait_limit_reel_count'
S_WAIT_LIMIT_REEL_HOURS  = 'wait_limit_reel_hours'
S_WAIT_LIMIT_STORY_COUNT = 'wait_limit_story_count'
S_WAIT_LIMIT_STORY_HOURS = 'wait_limit_story_hours'
S_WAIT_WEBSITE_URL    = 'wait_website_url'
S_WAIT_WELCOME_MSG    = 'wait_welcome_msg'
S_WAIT_TWITTER_WELCOME_MSG   = 'wait_twitter_welcome_msg'
S_WAIT_INSTAGRAM_WELCOME_MSG = 'wait_instagram_welcome_msg'
S_WAIT_START_OP_MSG   = 'wait_start_op_msg'
S_WAIT_END_OP_MSG     = 'wait_end_op_msg'
S_WAIT_VIP_ID         = 'wait_vip_id'
S_WAIT_INSTAGRAM_VIP_ID = 'wait_instagram_vip_id'
S_WAIT_ADMIN_CONTACT  = 'wait_admin_contact'
S_WAIT_LOCK_MSG       = 'wait_lock_msg'
S_WAIT_FLOOD_MSG      = 'wait_flood_msg'
S_WAIT_GROUP_NAME     = 'wait_group_name'
S_WAIT_TRANSFER_SRC   = 'wait_transfer_src'
S_WAIT_QUICK_ACCESS_MSG = 'wait_quick_access_msg'
S_WAIT_GUIDE_MSG        = 'wait_guide_msg'

# پنل ورود (یوزرنیم/پسورد) و مدیریت ناحیه‌ها — فقط ادمین کاربر پنل می‌سازد
S_WAIT_PU_LOGIN_USERNAME = 'wait_pu_login_username'
S_WAIT_PU_LOGIN_PASSWORD = 'wait_pu_login_password'
S_WAIT_OWNER_LOGIN_USERNAME = 'wait_owner_login_username'
S_WAIT_OWNER_LOGIN_PASSWORD = 'wait_owner_login_password'
S_WAIT_OWNER_LINK_CODE  = 'wait_owner_link_code'
S_WAIT_ZONE_NAME         = 'wait_zone_name'
S_WAIT_GROUP_HASHTAG_ZONE = 'wait_group_hashtag_zone'   # منتظر انتخاب ناحیه با دکمه (نه متن)

# افزودن کاربر پنل توسط ادمین
S_WAIT_ADMIN_PU_ZONE     = 'wait_admin_pu_zone'      # منتظر انتخاب ناحیه با دکمه
S_WAIT_ADMIN_PU_USERNAME = 'wait_admin_pu_username'
S_WAIT_ADMIN_PU_PASSWORD = 'wait_admin_pu_password'
# ایمپورتِ دسته‌ایِ کاربر از فایلِ اکسل: مرحله‌ی اول منتظرِ خودِ فایل،
# مرحله‌ی دوم (بعدِ پارس‌شدنِ موفق) منتظرِ انتخابِ ناحیه با دکمه - جفت‌های
# یوزرنیم/پسورد همون لحظه تویِ state_data نگه داشته می‌شن (نه دیتابیس،
# چون فقط تا لحظه‌ی انتخابِ ناحیه لازمن).
S_WAIT_ADMIN_XLSX_FILE      = 'wait_admin_xlsx_file'
S_WAIT_ADMIN_XLSX_ZONE_PICK = 'wait_admin_xlsx_zone_pick'
# فازِ ۸ (یکسان‌سازیِ بات↔اپ): ساختِ دسته‌ایِ N کاربرِ رندوم برایِ یک
# ناحیه - معادلِ باتیِ همون چیزی که تویِ اپ زیرِ «ساختِ دسته‌ای» هست.
S_WAIT_ADMIN_BULK_COUNT = 'wait_admin_bulk_count'
# فازِ ۸ (نقشِ فرمانده تویِ بات): این‌ها دقیقاً معادلِ باتیِ همون فلوهایی
# هستن که تویِ اپ زیرِ «کاربرها/ناحیه‌ها»ست، فقط با چکِ مجوزهایِ
# COMMANDER_PERMISSIONS به‌جایِ owner/admin بودن.
S_WAIT_CMD_PU_USERNAME = 'wait_cmd_pu_username'
S_WAIT_CMD_PU_PASSWORD = 'wait_cmd_pu_password'
S_WAIT_CMD_ZONE_NAME   = 'wait_cmd_zone_name'
S_WAIT_PEOPLE_USERNAME   = 'wait_people_username'    # افزودن سرپرست (افراد)

# FIX: اعداد 1-8 از escape keywords حذف شدن
_PRIVATE_ESCAPE_KEYWORDS = {
    'تنظیمات', 'شروع عملیات', 'پایان عملیات', 'گروه ها', 'پشتیبان گیری',
    'وضعیت', 'محدودیت', 'پیام', 'ادمین',
    'محتوای توییتر 🐦', 'محتوای اینستاگرام 📸',
    'دریافت متن', 'دریافت عکس', 'دریافت ریلز', 'دریافت استوری',
    'هشتگ چیست؟', '📊 وضعیت من', 'بازگشت به صفحه اصلی',
    'وب سایت',
    'ارتباط با ادمین', '📞 ارتباط با ادمین',
    'دکمه دسترسی هشتگ متن', 'دسترسی هشتگ متن',
    '🔐 حساب کاربری', '🔐 ورود به حساب', '👤 ورود مهمان', '👁 افراد تحت من', '📖 راهنما',
}

# ─────────────────────────────────────────────────────────────────────────────
# State helpers
# ─────────────────────────────────────────────────────────────────────────────
def get_state(uid, cid):
    with _states_lock:
        return _states.get((uid, cid), {})

def set_state(uid, cid, state, **data):
    with _states_lock:
        _states[(uid, cid)] = {'state': state, 'data': data, 'set_at': datetime.utcnow()}

def clear_state(uid, cid):
    with _states_lock:
        _states.pop((uid, cid), None)

def cur_state(uid, cid):
    with _states_lock:
        return _states.get((uid, cid), {}).get('state')

def state_data(uid, cid):
    with _states_lock:
        return _states.get((uid, cid), {}).get('data', {})

# ─────────────────────────────────────────────────────────────────────────────
# Admin zone context — هنگام پیمایش پنل «محدودیت‌ها» یا «ویرایش پیام‌ها»،
# ناحیه‌ی انتخاب‌شده اینجا نگه داشته می‌شود (مستقل از state متن‌ورودی بالا،
# چون با فشردن دکمه‌های اینلاین پاک نمی‌شود).
# ─────────────────────────────────────────────────────────────────────────────
_admin_zone_ctx: dict = {}
_admin_zone_ctx_lock = threading.Lock()

def set_admin_zone_ctx(uid, cid, zone_id):
    with _admin_zone_ctx_lock:
        _admin_zone_ctx[(uid, cid)] = zone_id

def get_admin_zone_ctx(uid, cid):
    with _admin_zone_ctx_lock:
        return _admin_zone_ctx.get((uid, cid))

# ─────────────────────────────────────────────────────────────────────────────
# People (افراد) selection — هنگام تعیین ناحیه‌های سرپرستی یک فرد، ست
# ناحیه‌های در حال انتخاب اینجا نگه داشته می‌شه (تا با هر تپ روی دکمه‌های
# ✅/❌ تغییر کنه، بدون نیاز به هر بار خوندن/نوشتن دیتابیس).
# ─────────────────────────────────────────────────────────────────────────────
_people_selection: dict = {}
_people_selection_lock = threading.Lock()

def set_people_selection(uid, cid, pu_id, zone_ids):
    with _people_selection_lock:
        _people_selection[(uid, cid)] = {'pu_id': pu_id, 'zone_ids': set(zone_ids)}

def get_people_selection(uid, cid):
    with _people_selection_lock:
        return _people_selection.get((uid, cid))

def toggle_people_zone(uid, cid, zone_id):
    with _people_selection_lock:
        sel = _people_selection.get((uid, cid))
        if not sel:
            return None
        if zone_id in sel['zone_ids']:
            sel['zone_ids'].discard(zone_id)
        else:
            sel['zone_ids'].add(zone_id)
        return sel

def set_people_zones_all(uid, cid, all_zone_ids, select: bool):
    with _people_selection_lock:
        sel = _people_selection.get((uid, cid))
        if not sel:
            return None
        sel['zone_ids'] = set(all_zone_ids) if select else set()
        return sel

def clear_people_selection(uid, cid):
    with _people_selection_lock:
        _people_selection.pop((uid, cid), None)

# ─────────────────────────────────────────────────────────────────────────────
# Export zone selection (فازِ ۸) — چک‌باکسِ چندناحیه‌ایِ اکسپورت؛ عمداً از
# _people_selection جدا نگه داشته شده چون معنایِ «confirm» و «remove» اونجا
# مخصوصِ نقشِ سرپرستیه، نه اکسپورت.
# ─────────────────────────────────────────────────────────────────────────────
_export_selection: dict = {}
_export_selection_lock = threading.Lock()

def init_export_selection(uid, cid, zone_ids=()):
    with _export_selection_lock:
        _export_selection[(uid, cid)] = set(zone_ids)

def get_export_selection(uid, cid):
    with _export_selection_lock:
        return _export_selection.get((uid, cid))

def toggle_export_zone(uid, cid, zone_id):
    with _export_selection_lock:
        sel = _export_selection.get((uid, cid))
        if sel is None:
            return None
        if zone_id in sel: sel.discard(zone_id)
        else: sel.add(zone_id)
        return sel

def set_export_zones_all(uid, cid, all_zone_ids, select: bool):
    with _export_selection_lock:
        if (uid, cid) not in _export_selection:
            return None
        _export_selection[(uid, cid)] = set(all_zone_ids) if select else set()
        return _export_selection[(uid, cid)]

def clear_export_selection(uid, cid):
    with _export_selection_lock:
        _export_selection.pop((uid, cid), None)

# ─────────────────────────────────────────────────────────────────────────────
# Hashtag zone selection — هنگام ساخت هشتگ/گروه بدون‌هشتگ، ناحیه‌های
# انتخاب‌شده اینجا نگه داشته می‌شه تا با هر تپ روی ✅/❌ تغییر کنه.
# ─────────────────────────────────────────────────────────────────────────────
_ht_zone_selection: dict = {}
_ht_zone_selection_lock = threading.Lock()

def set_ht_zone_selection(uid, cid, ht_text, append_tag, zone_ids=()):
    with _ht_zone_selection_lock:
        _ht_zone_selection[(uid, cid)] = {'ht_text': ht_text, 'append_tag': append_tag, 'zone_ids': set(zone_ids)}

def get_ht_zone_selection(uid, cid):
    with _ht_zone_selection_lock:
        return _ht_zone_selection.get((uid, cid))

def toggle_ht_zone(uid, cid, zone_id):
    with _ht_zone_selection_lock:
        sel = _ht_zone_selection.get((uid, cid))
        if not sel:
            return None
        if zone_id in sel['zone_ids']:
            sel['zone_ids'].discard(zone_id)
        else:
            sel['zone_ids'].add(zone_id)
        return sel

def set_ht_zones_all(uid, cid, all_zone_ids, select: bool):
    with _ht_zone_selection_lock:
        sel = _ht_zone_selection.get((uid, cid))
        if not sel:
            return None
        sel['zone_ids'] = set(all_zone_ids) if select else set()
        return sel

def clear_ht_zone_selection(uid, cid):
    with _ht_zone_selection_lock:
        _ht_zone_selection.pop((uid, cid), None)

# ─────────────────────────────────────────────────────────────────────────────
# Error reporter
# ─────────────────────────────────────────────────────────────────────────────
def report_error(context: str, error: Exception):
    log.error('%s: %s', context, error)
    owner_id = db.get_owner_id()
    if not owner_id:
        return  # هنوز مالک شناسایی نشده (هنوز کسی با /ownerlogin وارد نشده)
    try:
        now_ir = datetime.now(ZoneInfo('Asia/Tehran'))
        bot.send_message(
            owner_id,
            f'🔴 <b>خطای ربات</b>\n\n'
            f'بخش: <code>{_html.escape(context)}</code>\n'
            f'زمان: {now_ir.strftime("%H:%M")} (تهران)\n'
            f'جزئیات: <code>{_html.escape(str(error))}</code>',
            parse_mode='HTML'
        )
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Safe handler decorator
# ─────────────────────────────────────────────────────────────────────────────
def _extract_cid(update):
    """چه ورودی پیام باشه چه callback query، چت مربوطه رو پیدا می‌کنه."""
    try:
        return update.chat.id            # Message
    except AttributeError:
        pass
    try:
        return update.message.chat.id    # CallbackQuery
    except AttributeError:
        pass
    return None

def _extract_uid(update):
    """چه Message باشه چه CallbackQuery، هر دو یه from_user مستقیم دارن."""
    try:
        return update.from_user.id
    except AttributeError:
        return None

def _is_transient_network_error(e: Exception) -> bool:
    """
    خطاهایی مثل قطعی لحظه‌ای SSL یا ریست شدن کانکشن، معمولاً با یه تلاش
    دوباره (چند ثانیه بعد) خودشون حل می‌شن — چون واقعاً یه لحظه شبکه قطع
    بوده، نه یه باگ منطقی. برای این‌ها به‌جای نشون دادن فوری خطا به کاربر،
    خودمون چند بار دیگه امتحان می‌کنیم.
    """
    name = type(e).__name__
    text = str(e)
    markers = (
        'ConnectionError', 'ConnectionReset', 'ConnectionAborted',
        'ConnectionRefused', 'Timeout', 'SSLError', 'SSLEOFError',
        'RemoteDisconnected', 'ProtocolError', 'ReadTimeout', 'ChunkedEncodingError',
    )
    return any(m in name or m in text for m in markers)

def _safe_handler(func, max_retries: int = 2, retry_delay: float = 2.0):
    """
    محافظ همه‌ی هندلرهای اصلی: قبل از این، اگه یه خطای غیرمنتظره (مثلاً قفل
    لحظه‌ای دیتابیس یا یه None غیرمنتظره) وسط پردازش یه پیام رخ می‌داد، کاربر
    هیچ پیامی نمی‌گرفت و هیچ‌جا هم ثبت نمی‌شد — دقیقاً همون «گاهی‌وقتا ربات
    هیچی نمی‌ده» که هیچ ردی ازش نبود.

    برای خطاهای گذرای شبکه (SSL/Connection/Timeout)، به‌جای نشون دادن فوری
    پیام خطا، خودش چند بار (پیش‌فرض ۲ بار، با فاصله‌ی چند ثانیه) دوباره کل
    هندلر رو اجرا می‌کنه؛ اگه یکی از این تلاش‌ها موفق شد، کاربر اصلاً متوجه‌ی
    هیچ مشکلی نمی‌شه. فقط اگه همه‌ی تلاش‌ها با شکست مواجه شدن (یا خطا از نوع
    گذرای شبکه نبود)، پیام «خطای موقتی» نشون داده می‌شه و جزئیات برای
    OWNER_ID فرستاده می‌شه.
    """
    @functools.wraps(func)
    def wrapper(update, *args, **kwargs):
        # چکِ دسترسیِ «بات» - قبل از هر چیز دیگه، همینجا (یه گلوگاهِ واحد
        # برای همه‌ی هندلرهای پیوی/گروه/callback). مالک و ادمین‌های بات
        # هیچ‌وقت محدود نمی‌شن. کاربری که هنوز عضوِ ثبت‌شده نیست (pu=None،
        # مثلاً داره اولین بار /start می‌زنه) هم بلاک نمی‌شه - این محدودیت
        # فقط برای اعضای از قبل ثبت‌شده معنی داره.
        uid = _extract_uid(update)
        if uid is not None and not is_bot_admin_or_owner(uid):
            pu = db.get_panel_user_by_telegram_id(uid)
            if pu and not db.user_has_service_access(pu["id"], "bot"):
                cid = _extract_cid(update)
                if cid:
                    try:
                        bot.send_message(cid, db.get_access_denied_msg(pu["zone_id"]))
                    except Exception:
                        pass
                return
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                return func(update, *args, **kwargs)
            except Exception as e:
                last_exc = e
                if _is_transient_network_error(e) and attempt < max_retries:
                    log.warning(
                        'Transient error in %s (attempt %d/%d), retrying in %.1fs: %s',
                        func.__name__, attempt + 1, max_retries, retry_delay, e
                    )
                    time.sleep(retry_delay)
                    continue
                break
        log.error('Handler %s failed after retries: %s', func.__name__, last_exc, exc_info=True)
        report_error(f'Handler: {func.__name__}', last_exc)
        cid = _extract_cid(update)
        if cid:
            try:
                bot.send_message(cid, '⚠️ یک خطای موقتی رخ داد، لطفاً دوباره تلاش کنید.')
            except Exception:
                pass
    return wrapper

# ─────────────────────────────────────────────────────────────────────────────
# Permission helpers
# ─────────────────────────────────────────────────────────────────────────────
def is_owner(uid):               return uid is not None and (uid == db.get_owner_id() or db.is_extra_owner(uid))
def is_bot_admin_or_owner(uid):  return is_owner(uid) or db.is_bot_admin(uid)

def commander_pu(uid):
    """اگه این uid (چت‌آیدیِ تلگرام) به یک panel_user لینک شده و اون
    panel_user فرمانده‌ست، خودِ رکوردِ panel_user رو برمی‌گردونه، وگرنه
    None. برایِ گیت‌کردنِ کالبک‌ها/دستورهایِ پنلِ فرمانده تویِ بات."""
    pu = db.get_panel_user_by_telegram_id(uid)
    if pu and db.is_commander(pu['id']):
        return pu
    return None
def is_admin_or_owner(uid):      return is_owner(uid) or db.is_bot_admin(uid) or db.is_group_admin(uid)
def is_group_chat(t):            return t in ('group', 'supergroup')

def format_wait_time(reset_at: datetime) -> str:
    diff   = reset_at - datetime.utcnow()
    total  = max(0, int(diff.total_seconds()))
    h      = total // 3600
    m      = (total % 3600) // 60
    s      = total % 60
    if h > 0:  return f'{h} ساعت و {m} دقیقه و {s} ثانیه'
    if m > 0:  return f'{m} دقیقه و {s} ثانیه'
    return f'{s} ثانیه'

# ─────────────────────────────────────────────────────────────────────────────
# Keyboards — main menus
# ─────────────────────────────────────────────────────────────────────────────
def _edit_panel(cid, mid, text, kb, parse_mode='HTML'):
    try:
        bot.edit_message_text(text, cid, mid, parse_mode=parse_mode, reply_markup=kb)
    except Exception:
        bot.send_message(cid, text, parse_mode=parse_mode, reply_markup=kb)

# ─────────────────────────────────────────────────────────────────────────────
# Admin status pin message
# ─────────────────────────────────────────────────────────────────────────────
