# -*- coding: utf-8 -*-
"""تمام کیبوردهای Reply و Inline ربات (ساخت دکمه‌ها) — بدون منطق دیگر."""
import html as _html
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

from base import database as db

def user_main_menu(supervisor=False, commander=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton('محتوای توییتر 🐦'))
    kb.row(KeyboardButton('محتوای اینستاگرام 📸'))
    if db.get_website_status():
        kb.row(KeyboardButton('وب سایت'))
    kb.row(KeyboardButton('هشتگ چیست؟'), KeyboardButton('📊 وضعیت من'))
    kb.row(KeyboardButton('📖 راهنما'), KeyboardButton('🔐 حساب کاربری'))
    if supervisor:
        kb.row(KeyboardButton('👁 افراد تحت من'))
    if commander:
        kb.row(KeyboardButton('🎖 پنل فرمانده'))
    kb.row(KeyboardButton('📞 ارتباط با ادمین'))
    return kb

def _quick_access_kb():
    """۴ دکمه‌ی عملیاتی + ۲ عنوان بدون عملکرد (فقط اسم گروه ستون‌ها) — زیر
    پیام خوش‌آمد اصلی، فقط وقتی عملیات فعال است."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton('محتوای توییتر', callback_data='noop'),
        InlineKeyboardButton('محتوای اینستاگرام', callback_data='noop'),
    )
    kb.row(
        InlineKeyboardButton('متن', callback_data='quick:text'),
        InlineKeyboardButton('ریلز', callback_data='quick:reel'),
    )
    kb.row(
        InlineKeyboardButton('عکس', callback_data='quick:photo'),
        InlineKeyboardButton('استوری', callback_data='quick:story'),
    )
    return kb

def twitter_panel_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton('دریافت متن'))
    kb.add(KeyboardButton('دریافت عکس'))
    kb.row(KeyboardButton('هشتگ چیست؟'), KeyboardButton('📊 وضعیت من'))
    kb.add(KeyboardButton('بازگشت به صفحه اصلی'))
    return kb

def instagram_panel_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton('دریافت ریلز'))
    kb.add(KeyboardButton('دریافت استوری'))
    kb.row(KeyboardButton('هشتگ چیست؟'), KeyboardButton('📊 وضعیت من'))
    kb.add(KeyboardButton('بازگشت به صفحه اصلی'))
    return kb

def owner_settings_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton('شروع عملیات',    callback_data='owner:start_op'),
        InlineKeyboardButton('پایان عملیات',   callback_data='owner:stop_op'),
    )
    kb.add(
        InlineKeyboardButton('گروه ها',        callback_data='owner:groups'),
        InlineKeyboardButton('پشتیبان گیری',  callback_data='owner:backup'),
    )
    kb.add(
        InlineKeyboardButton('وضعیت 📈',      callback_data='owner:status'),
        InlineKeyboardButton('محدودیت ⚙️',    callback_data='owner:limit'),
    )
    kb.add(
        InlineKeyboardButton('ادمین 👤',       callback_data='owner:bot_admins'),
        InlineKeyboardButton('وب سایت 🌐',    callback_data='owner:website'),
    )
    kb.add(InlineKeyboardButton('ویرایش پیام‌ها 📝', callback_data='owner:msg_settings'))
    kb.add(InlineKeyboardButton('👑  VIP',            callback_data='owner:vip'))
    kb.add(InlineKeyboardButton('🔧 دسترسی هشتگ متن', callback_data='owner:ht_access'))
    kb.add(InlineKeyboardButton('🔐 پنل کاربران (نواحی)', callback_data='owner:zones'))
    kb.add(InlineKeyboardButton('👥 افراد', callback_data='owner:people'))
    kb.add(InlineKeyboardButton('📤 اکسپورتِ اکسل', callback_data='owner:export_menu'))
    return kb

# ─────────────────────────────────────────────────────────────────────────────
# Keyboards — helpers
# ─────────────────────────────────────────────────────────────────────────────
def _btn_home():                return InlineKeyboardButton('🔙 برگشت به خانه', callback_data='owner:home')
def _btn_back(target: str):     return InlineKeyboardButton('⬅️ برگشت به عقب', callback_data=target)
def _cancel_kb(back: str):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton('❌ لغو', callback_data=back))
    return kb
def _confirm_kb(yes_cb: str, no_cb: str):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('بله ✅', callback_data=yes_cb),
           InlineKeyboardButton('خیر ❌', callback_data=no_cb))
    return kb

def hashtags_inline(prefix: str):
    kb = InlineKeyboardMarkup(row_width=2)
    for ht in db.get_all_hashtags():
        kb.add(InlineKeyboardButton(ht['name'], callback_data=f'{prefix}:{ht["id"]}'))
    return kb

def confirm_delete_hashtag_kb(hid: int):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('بله ✅', callback_data=f'confirm_del_ht:{hid}'),
           InlineKeyboardButton('خیر ❌', callback_data='cancel_del_ht'))
    return kb

# ─────────────────────────────────────────────────────────────────────────────
# Keyboards — settings panels
# ─────────────────────────────────────────────────────────────────────────────
def _status_kb():
    kb = InlineKeyboardMarkup()
    kb.add(_btn_home())
    return kb

def _limit_kb(zone_id=None):
    """سطح اول: انتخاب بین محدودیت توییتر یا اینستاگرام (برای ناحیه‌ی زیر)."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('توییتر 🐦', callback_data='owner:limit_twitter'))
    kb.add(InlineKeyboardButton('اینستاگرام 📸', callback_data='owner:limit_instagram'))
    kb.add(InlineKeyboardButton('🔁 تغییر ناحیه', callback_data='owner:limit'))
    kb.add(_btn_home())
    return kb

def _limit_twitter_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f'متن ({db.get_text_allowance(zone_id)} تا)', callback_data='limit:texts'),
        InlineKeyboardButton(f'ساعت ({db.get_cooldown_hours(zone_id)} ساعت)', callback_data='limit:hours'),
    )
    kb.add(_btn_back('owner:limit'), _btn_home())
    return kb

def _limit_instagram_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('ریلز', callback_data='owner:limit_reel'))
    kb.add(InlineKeyboardButton('استوری', callback_data='owner:limit_story'))
    kb.add(_btn_back('owner:limit'), _btn_home())
    return kb

def _limit_reel_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f'تعداد ({db.get_reel_limit(zone_id)} تا)', callback_data='limit:reel_count'),
        InlineKeyboardButton(f'ساعت ({db.get_reel_cooldown_hours(zone_id)} ساعت)', callback_data='limit:reel_hours'),
    )
    kb.add(_btn_back('owner:limit_instagram'), _btn_home())
    return kb

def _limit_story_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f'تعداد ({db.get_story_limit(zone_id)} تا)', callback_data='limit:story_count'),
        InlineKeyboardButton(f'ساعت ({db.get_story_cooldown_hours(zone_id)} ساعت)', callback_data='limit:story_hours'),
    )
    kb.add(_btn_back('owner:limit_instagram'), _btn_home())
    return kb

def _limit_input_kb(back_to: str = 'owner:limit_twitter'):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(_btn_back(back_to), _btn_home())
    return kb

def _groups_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('ادمین گروه 👥', callback_data='owner:group_admins'))
    kb.add(_btn_home())
    return kb

def _groups_empty_kb():
    kb = InlineKeyboardMarkup()
    kb.add(_btn_home())
    return kb

def _group_admins_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('حذف ❌',    callback_data='owner:remove_admin_list'),
           InlineKeyboardButton('افزودن ➕', callback_data='owner:add_admin'))
    kb.add(_btn_back('owner:groups'), _btn_home())
    return kb

def _group_admins_remove_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for a in db.get_all_group_admins():
        pu_row = db.get_panel_user_by_telegram_id(a["user_id"]); lbl = pu_row["username"] if pu_row else (a.get('first_name') or str(a['user_id']))
        kb.add(InlineKeyboardButton(f'❌ {lbl}', callback_data=f'remove_admin:{a["user_id"]}'))
    kb.add(_btn_back('owner:group_admins'), _btn_home())
    return kb

def _bot_admins_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('افزودن ➕', callback_data='bot_admin:add'),
           InlineKeyboardButton('حذف ❌',   callback_data='bot_admin:remove_list'))
    kb.add(_btn_home())
    return kb

def _bot_admins_remove_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for a in db.get_all_bot_admins():
        pu_row = db.get_panel_user_by_telegram_id(a["user_id"]); lbl = pu_row["username"] if pu_row else (a.get('first_name') or str(a['user_id']))
        kb.add(InlineKeyboardButton(f'❌ {lbl}', callback_data=f'remove_bot_admin:{a["user_id"]}'))
    kb.add(_btn_back('owner:bot_admins'), _btn_home())
    return kb

def _website_kb():
    enabled = db.get_website_status()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('تغییر وب سایت 🔗',  callback_data='website:change_url'))
    kb.add(InlineKeyboardButton('❌ غیر فعال کردن' if enabled else '✅ فعال کردن',
                                callback_data='website:toggle'))
    kb.add(_btn_home())
    return kb

def _website_change_url_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(_btn_back('owner:website'), _btn_home())
    return kb

def _msg_settings_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('پیام خوش‌آمدگویی',              callback_data='msg:preview:welcome'))
    kb.add(InlineKeyboardButton('پیام پنل توییتر 🐦',            callback_data='msg:preview:twitter_welcome'))
    kb.add(InlineKeyboardButton('پیام پنل اینستاگرام 📸',        callback_data='msg:preview:instagram_welcome'))
    kb.add(InlineKeyboardButton('پیام شروع عملیات',              callback_data='msg:preview:start_op'))
    kb.add(InlineKeyboardButton('پیام پایان عملیات',             callback_data='msg:preview:end_op'))
    kb.add(InlineKeyboardButton('پیام قفل 🔒',                   callback_data='msg:preview:lock'))
    kb.add(InlineKeyboardButton('ارتباط با ادمین',               callback_data='msg:preview:contact'))
    kb.add(InlineKeyboardButton('پیام کاربر در حال اذیت کردن ربات', callback_data='msg:preview:flood'))
    kb.add(InlineKeyboardButton('پیام دسترسی سریع ⚡️',           callback_data='msg:preview:quick_access'))
    kb.add(InlineKeyboardButton('📖 راهنما',                     callback_data='msg:preview:guide'))
    if db.is_quick_access_enabled():
        kb.add(InlineKeyboardButton('❌ غیرفعال کردن پنل دریافت سریع محتوا', callback_data='msg:toggle_quick_access'))
    else:
        kb.add(InlineKeyboardButton('✅ فعال کردن پنل دریافت سریع محتوا', callback_data='msg:toggle_quick_access'))
    kb.add(InlineKeyboardButton('🔁 تغییر ناحیه', callback_data='owner:msg_settings'))
    kb.add(_btn_home())
    return kb

def _msg_edit_kb(back_to: str):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(_btn_back(back_to), _btn_home())
    return kb

# ─────────────────────────────────────────────────────────────────────────────
# Keyboards — پنل ورود کاربران (حساب کاربری) + مدیریت ناحیه‌ها
# ─────────────────────────────────────────────────────────────────────────────

def account_menu_kb(logged_in: bool):
    kb = InlineKeyboardMarkup(row_width=1)
    if logged_in:
        kb.add(InlineKeyboardButton('🚪 خروج از حساب', callback_data='account:logout'))
    else:
        kb.add(InlineKeyboardButton('🔓 ورود', callback_data='account:login'))
    return kb

def login_required_kb():
    """کیبورد پایین صفحه (Reply Keyboard) پیش از ورود — دکمه‌ی ورود، و
    اگه مالک فعالش کرده باشه، دکمه‌ی ورود مهمان هم زیرش."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton('🔐 ورود به حساب'))
    if db.is_guest_login_enabled() and db.get_guest_zone_id():
        kb.row(KeyboardButton('👤 ورود مهمان'))
    return kb

def zone_pick_kb(prefix: str = 'admin_pu_zone_pick', include_all: bool = False):
    """انتخاب ناحیه (مثلا هنگام ساخت کاربر پنل توسط ادمین). include_all=True
    یه دکمه‌ی «🌐 همگانی» هم اضافه می‌کنه (callback: f'{prefix}:all')."""
    kb = InlineKeyboardMarkup(row_width=1)
    for z in db.get_all_zones():
        kb.add(InlineKeyboardButton(z['name'], callback_data=f'{prefix}:{z["id"]}'))
    if include_all:
        kb.add(InlineKeyboardButton('🌐 همگانی (پیش‌فرض همه‌ی ناحیه‌ها)', callback_data=f'{prefix}:all'))
    return kb

def owner_zones_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for z in db.get_all_zones():
        cnt = db.count_zone_users(z['id'])
        kb.add(InlineKeyboardButton(f'📁 {z["name"]} ({cnt} کاربر)', callback_data=f'zone:open:{z["id"]}'))
    kb.add(InlineKeyboardButton('➕ افزودن ناحیه', callback_data='zone:add'))
    kb.add(InlineKeyboardButton('👤 افزودن کاربر پنل', callback_data='admin_pu:add'))
    kb.add(InlineKeyboardButton('📊 ایمپورتِ کاربرها از اکسل', callback_data='admin_pu:import_xlsx'))
    guest_label = '👤 ورود مهمان: ✅ فعال (برای خاموش‌کردن بزن)' if db.is_guest_login_enabled() \
        else '👤 ورود مهمان: ❌ غیرفعال (برای فعال‌کردن بزن)'
    kb.add(InlineKeyboardButton(guest_label, callback_data='owner:toggle_guest_login'))
    kb.add(_btn_home())
    return kb

def export_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('📤 همه‌ی کاربرها', callback_data='export:all'))
    kb.add(InlineKeyboardButton('📤 ناحیه‌های دلخواه', callback_data='export:pick_zones'))
    kb.add(_btn_back('owner:home'), _btn_home())
    return kb

def export_zone_select_kb(selected_zone_ids):
    selected = set(selected_zone_ids)
    zones = db.get_all_zones()
    kb = InlineKeyboardMarkup(row_width=1)
    for z in zones:
        mark = '✅' if z['id'] in selected else '❌'
        kb.add(InlineKeyboardButton(f'{mark} {z["name"]}', callback_data=f'export:toggle:{z["id"]}'))
    all_selected = zones and len(selected) == len(zones)
    kb.add(InlineKeyboardButton('❌ لغو همه' if all_selected else '✅ انتخاب همه', callback_data='export:toggle_all'))
    kb.add(InlineKeyboardButton('📤 اکسپورتِ انتخاب‌شده‌ها', callback_data='export:confirm'))
    kb.add(_btn_back('owner:export_menu'), _btn_home())
    return kb

def zone_detail_kb(zone_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    for u in db.get_panel_users_by_zone(zone_id):
        kb.add(InlineKeyboardButton(f'👤 {u["username"]}', callback_data=f'puser:open:{u["id"]}'))
    kb.add(InlineKeyboardButton('➕ افزودن کاربر به این ناحیه', callback_data=f'admin_pu_zone_pick:{zone_id}'))
    kb.add(InlineKeyboardButton('➕➕ ساختِ دسته‌ای (رندوم)', callback_data=f'zone_bulk_create:{zone_id}'))
    kb.add(InlineKeyboardButton('🔧 دسترسیِ سرویسِ این ناحیه', callback_data=f'zone_services:{zone_id}'))
    kb.add(InlineKeyboardButton('📤 اکسپورتِ این ناحیه', callback_data=f'export:zone:{zone_id}'))
    if db.get_guest_zone_id() == zone_id:
        kb.add(InlineKeyboardButton('📌 ناحیه‌ی مهمان‌ها ✅ (برای لغو بزن)', callback_data=f'zone:unset_guest:{zone_id}'))
    else:
        kb.add(InlineKeyboardButton('📌 تنظیم به‌عنوان ناحیه‌ی مهمان‌ها', callback_data=f'zone:set_guest:{zone_id}'))
    kb.add(InlineKeyboardButton('🗑 حذف این ناحیه', callback_data=f'zone:delete_confirm:{zone_id}'))
    kb.add(_btn_back('owner:zones'), _btn_home())
    return kb

# فازِ ۸: دسترسیِ سرویس (app/bot/site) - هم برایِ کلِ یک ناحیه، هم
# override شخصیِ یک کاربرِ خاص. کلیدها با ALL_SERVICES تویِ database.py
# یکی‌ان: 'app', 'bot', 'site'.
_SERVICE_BTN_LABELS = {'app': '📱 اپ', 'bot': '🤖 بات', 'site': '🌐 سایت'}

def zone_services_kb(zone_id: int, current: set):
    kb = InlineKeyboardMarkup(row_width=1)
    for key, label in _SERVICE_BTN_LABELS.items():
        mark = '✅' if key in current else '◻️'
        kb.add(InlineKeyboardButton(f'{mark} {label}', callback_data=f'zone_services_toggle:{zone_id}:{key}'))
    kb.add(_btn_back(f'zone:open:{zone_id}'), _btn_home())
    return kb

def puser_services_kb(pu_id: int, effective: set, has_override: bool, back_cb: str | None = None):
    kb = InlineKeyboardMarkup(row_width=1)
    for key, label in _SERVICE_BTN_LABELS.items():
        mark = '✅' if key in effective else '◻️'
        kb.add(InlineKeyboardButton(f'{mark} {label}', callback_data=f'puser_services_toggle:{pu_id}:{key}'))
    if has_override:
        kb.add(InlineKeyboardButton('↩️ بازگشت به تنظیمِ ناحیه', callback_data=f'puser_services_reset:{pu_id}'))
    kb.add(InlineKeyboardButton('⬅️ برگشت به عقب', callback_data=back_cb or f'puser:open:{pu_id}'), _btn_home())
    return kb

def zone_delete_confirm_kb(zone_id: int):
    return _confirm_kb(f'zone:delete_do:{zone_id}', f'zone:open:{zone_id}')

def panel_user_detail_kb(pu_id: int, zone_id: int, can_see_password: bool = False):
    kb = InlineKeyboardMarkup(row_width=1)
    if can_see_password:
        kb.add(InlineKeyboardButton('🔄 ریست پسورد', callback_data=f'puser:reset_pw:{pu_id}'))
    kb.add(InlineKeyboardButton('🔧 دسترسیِ سرویسِ این کاربر', callback_data=f'puser_services:{pu_id}'))
    kb.add(InlineKeyboardButton('🗑 حذف کاربر', callback_data=f'puser:delete_confirm:{pu_id}'))
    kb.add(_btn_back(f'zone:open:{zone_id}'), _btn_home())
    return kb

def panel_user_delete_confirm_kb(pu_id: int, zone_id: int):
    return _confirm_kb(f'puser:delete_do:{pu_id}', f'puser:open:{pu_id}')

def people_list_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for s in db.get_all_supervisors():
        zone_lbl = '، '.join(z['name'] for z in s['zones'])
        kb.add(InlineKeyboardButton(f'👤 {s["username"]} — {zone_lbl}', callback_data=f'people:edit:{s["id"]}'))
    kb.add(InlineKeyboardButton('➕ افزودن فرد', callback_data='people:add'))
    kb.add(_btn_home())
    return kb

def people_zone_select_kb(selected_zone_ids, pu_id):
    selected = set(selected_zone_ids)
    zones = db.get_all_zones()
    kb = InlineKeyboardMarkup(row_width=1)
    for z in zones:
        mark = '✅' if z['id'] in selected else '❌'
        kb.add(InlineKeyboardButton(f'{mark} {z["name"]}', callback_data=f'people:toggle:{z["id"]}'))
    all_selected = zones and len(selected) == len(zones)
    kb.add(InlineKeyboardButton('❌ لغو همه' if all_selected else '✅ انتخاب همه', callback_data='people:toggle_all'))
    kb.add(InlineKeyboardButton('✅ تایید و ذخیره', callback_data='people:confirm'))
    kb.add(InlineKeyboardButton('🗑 حذف نقش سرپرستی', callback_data=f'people:remove:{pu_id}'))
    kb.add(_btn_back('owner:people'), _btn_home())
    return kb

def supervisor_zones_kb(pu_id: int):
    """کیبورد خودِ سرپرست برای دیدن ناحیه‌هایی که بهش دسترسی داده شده."""
    kb = InlineKeyboardMarkup(row_width=1)
    zone_ids = db.get_supervisor_zone_ids(pu_id)
    for zid in zone_ids:
        z = db.get_zone(zid)
        if z:
            kb.add(InlineKeyboardButton(f'📁 {z["name"]}', callback_data=f'super:zone:{zid}'))
    return kb

# فازِ ۸ - نقشِ فرمانده تویِ بات. برخلافِ owner/admin که سطحِ دسترسی‌شون
# ثابته، این‌جا هر دکمه فقط وقتی نشون داده می‌شه که تویِ
# COMMANDER_PERMISSIONS واقعاً بهش اجازه داده شده باشه.
def commander_zones_kb(pu_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    for zid in db.get_commander_zone_ids(pu_id):
        z = db.get_zone(zid)
        if z:
            kb.add(InlineKeyboardButton(f'📁 {z["name"]}', callback_data=f'cmd:zone:{zid}'))
    if db.commander_has_permission(pu_id, 'zone.create'):
        kb.add(InlineKeyboardButton('➕ ساختِ ناحیه‌ی جدید', callback_data='cmd:zone_create'))
    return kb

def commander_zone_detail_kb(pu_id: int, zone_id: int, perms: set):
    kb = InlineKeyboardMarkup(row_width=1)
    for u in db.get_panel_users_by_zone(zone_id):
        kb.add(InlineKeyboardButton(f'👤 {u["username"]}', callback_data=f'cmd:puser:{u["id"]}'))
    if 'user.add' in perms:
        kb.add(InlineKeyboardButton('➕ افزودن کاربر', callback_data=f'cmd:puser_add:{zone_id}'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data='cmd:zones'))
    return kb

def commander_puser_detail_kb(pu_id: int, target_id: int, zone_id: int, perms: set):
    kb = InlineKeyboardMarkup(row_width=1)
    if 'user.reset_password' in perms:
        kb.add(InlineKeyboardButton('🔄 ریست پسورد', callback_data=f'cmd:puser_reset_pw:{target_id}'))
    if 'user.change_service_access' in perms:
        kb.add(InlineKeyboardButton('🔧 دسترسیِ سرویس', callback_data=f'puser_services:{target_id}'))
    if 'user.remove' in perms:
        kb.add(InlineKeyboardButton('🗑 حذف کاربر', callback_data=f'cmd:puser_remove_confirm:{target_id}'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data=f'cmd:zone:{zone_id}'))
    return kb

def commander_puser_remove_confirm_kb(target_id: int, zone_id: int):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton('✅ بله، حذف شود', callback_data=f'cmd:puser_remove:{target_id}'),
        InlineKeyboardButton('❌ انصراف', callback_data=f'cmd:puser:{target_id}'),
    )
    return kb

def username_candidates_kb(candidates: list, action: str):
    """
    لیست کاربران پیشنهادی برای انتخاب (پیدا شده با جستجوی یوزرنیم پنل). action
    مشخص می‌کنه این انتخاب برای چه کاریه (add_admin/add_bot_admin/add_vip/
    add_ig_vip) تا در callback_data قید بشه. candidates رکوردهای panel_users
    هستن (فیلد id، نه user_id).
    """
    kb = InlineKeyboardMarkup(row_width=1)
    for c in candidates:
        logged = ' ✅' if c.get('telegram_user_id') else ' ⚠️ هنوز وارد نشده'
        kb.add(InlineKeyboardButton(f'{c["username"]}{logged}', callback_data=f'ppick:{action}:{c["id"]}'))
    return kb

def _vip_kb():
    """سطح اول: انتخاب بین VIP توییتر یا اینستاگرام."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton('توییتر 🐦', callback_data='owner:vip_twitter'))
    kb.add(InlineKeyboardButton('اینستاگرام 📸', callback_data='owner:vip_instagram'))
    kb.add(_btn_home())
    return kb

def _vip_twitter_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('➕ افزودن VIP', callback_data='vip:add'),
           InlineKeyboardButton('➖ حذف VIP',   callback_data='vip:remove_list'))
    kb.add(_btn_back('owner:vip'), _btn_home())
    return kb

def _vip_remove_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for v in db.get_all_vip_users():
        pu_row = db.get_panel_user_by_telegram_id(v["user_id"]); lbl = pu_row["username"] if pu_row else (v.get('first_name') or str(v['user_id']))
        kb.add(InlineKeyboardButton(f'❌ {lbl}', callback_data=f'remove_vip:{v["user_id"]}'))
    kb.add(_btn_back('owner:vip_twitter'), _btn_home())
    return kb

def _instagram_vip_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('➕ افزودن VIP', callback_data='ig_vip:add'),
           InlineKeyboardButton('➖ حذف VIP',   callback_data='ig_vip:remove_list'))
    kb.add(_btn_back('owner:vip'), _btn_home())
    return kb

def _instagram_vip_remove_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for v in db.get_all_instagram_vip_users():
        pu_row = db.get_panel_user_by_telegram_id(v["user_id"]); lbl = pu_row["username"] if pu_row else (v.get('first_name') or str(v['user_id']))
        kb.add(InlineKeyboardButton(f'❌ {lbl}', callback_data=f'remove_ig_vip:{v["user_id"]}'))
    kb.add(_btn_back('owner:vip_instagram'), _btn_home())
    return kb

def _hashtag_start_op_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_all_hashtags():
        c = db.count_texts_by_hashtag(ht['id'])
        kb.add(InlineKeyboardButton(f'{ht["name"]}  ({c} متن)',
                                    callback_data=f'start_op_ht:{ht["id"]}'))
    return kb

def _hashtag_toggle_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_all_hashtags():
        c      = db.count_texts_by_hashtag(ht['id'])
        status = '✅' if ht.get('is_active') else '❌'
        prefix = '🏷' if ht.get('append_tag', 1) else '📁'
        kb.add(InlineKeyboardButton(f'{prefix} {ht["name"]} ({c}) {status}',
                                    callback_data=f'toggle_ht:{ht["id"]}'))
    kb.add(_btn_back('owner:home'), _btn_home())
    return kb

def _user_ht_select_kb(count: int, zone_id=None):
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_active_hashtags_for_zone(zone_id):
        prefix = '🏷' if ht.get('append_tag', 1) else '📁'
        kb.add(InlineKeyboardButton(f'{prefix} {ht["name"]}',
                                    callback_data=f'user_ht_txt:{ht["id"]}:{count}'))
    return kb

def _user_ht_photo_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_active_hashtags_for_zone(zone_id):
        prefix = '🏷' if ht.get('append_tag', 1) else '📁'
        kb.add(InlineKeyboardButton(f'{prefix} {ht["name"]}',
                                    callback_data=f'user_ht_photo:{ht["id"]}'))
    return kb

def _user_ht_reel_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_active_hashtags_for_zone(zone_id):
        prefix = '🏷' if ht.get('append_tag', 1) else '📁'
        kb.add(InlineKeyboardButton(f'{prefix} {ht["name"]}',
                                    callback_data=f'user_ht_reel:{ht["id"]}'))
    return kb

def _user_ht_story_kb(zone_id=None):
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_active_hashtags_for_zone(zone_id):
        prefix = '🏷' if ht.get('append_tag', 1) else '📁'
        kb.add(InlineKeyboardButton(f'{prefix} {ht["name"]}',
                                    callback_data=f'user_ht_story:{ht["id"]}'))
    return kb

def _group_zone_pick_kb():
    """قدیمی — دیگه استفاده نمی‌شه (جایگزین: ht_zone_select_kb چندانتخابی)."""
    kb = InlineKeyboardMarkup(row_width=1)
    for z in db.get_all_zones():
        kb.add(InlineKeyboardButton(z['name'], callback_data=f'grp:ht_zone_pick:{z["id"]}'))
    kb.add(InlineKeyboardButton('🌐 برای همه‌ی ناحیه‌ها', callback_data='grp:ht_zone_pick:all'))
    return kb

def ht_zone_select_kb(selected_zone_ids):
    """انتخاب چندتایی ناحیه برای هشتگ/گروه بدون‌هشتگ (✅/❌ + انتخاب‌همه)."""
    selected = set(selected_zone_ids)
    zones = db.get_all_zones()
    kb = InlineKeyboardMarkup(row_width=1)
    for z in zones:
        mark = '✅' if z['id'] in selected else '❌'
        kb.add(InlineKeyboardButton(f'{mark} {z["name"]}', callback_data=f'grp:htzone:toggle:{z["id"]}'))
    all_selected = zones and len(selected) == len(zones)
    kb.add(InlineKeyboardButton('❌ لغو همه' if all_selected else '✅ انتخاب همه', callback_data='grp:htzone:toggle_all'))
    kb.add(InlineKeyboardButton('✅ تایید و ذخیره', callback_data='grp:htzone:confirm'))
    kb.add(InlineKeyboardButton('لغو', callback_data='grp:back'))
    return kb

# ─────────────────────────────────────────────────────────────────────────────
# Keyboards — group /start panel
# ─────────────────────────────────────────────────────────────────────────────
def _group_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('➕ هشتگ', callback_data='grp:add_hashtag'),
           InlineKeyboardButton('➖ هشتگ', callback_data='grp:del_hashtag'))
    kb.add(InlineKeyboardButton('توییتر 🐦', callback_data='grp:twitter'))
    kb.add(InlineKeyboardButton('اینستاگرام 📸', callback_data='grp:instagram'))
    kb.add(InlineKeyboardButton('📁 محتوای بدون هشتگ', callback_data='grp:no_tag'))
    return kb

def _group_panel_text(cid: int) -> str:
    total_text  = db.count_texts()
    total_photo = sum(db.count_photos_by_hashtag(h['id']) for h in db.get_all_hashtags())
    total_reel  = sum(db.count_reels_by_hashtag(h['id']) for h in db.get_all_hashtags())
    total_story = sum(db.count_stories_by_hashtag(h['id']) for h in db.get_all_hashtags())
    active      = db.get_active_hashtags()
    ht_names    = ' | '.join(h['name'] for h in active) if active else 'هیچ‌کدام'
    all_hts     = db.get_all_hashtags()
    lines = [
        '📊 <b>تعداد کل محتوا:</b>',
        f'📝 متن: {total_text} | 🖼 عکس: {total_photo} | 🎬 ریلز: {total_reel} | ⭕️ استوری: {total_story}',
        '',
        f'🏷 هشتگ‌های فعال: {ht_names}',
        '',
        '📋 <b>لیست همه هشتگ‌ها (محتوای بدون‌هشتگ هم شامل می‌شود):</b>',
    ]
    for ht in all_hts:
        tc = db.count_texts_by_hashtag(ht['id'])
        pc = db.count_photos_by_hashtag(ht['id'])
        rc = db.count_reels_by_hashtag(ht['id'])
        sc = db.count_stories_by_hashtag(ht['id'])
        p  = '🏷' if ht.get('append_tag', 1) else '📁'
        am = ' ✅' if ht.get('is_active') else ''
        lines.append(
            f'{p} <b>{_html.escape(ht["name"])}</b>{am} — '
            f'متن: {tc} | عکس: {pc} | ریلز: {rc} | استوری: {sc}'
        )
    lines.append('')
    lines.append('لطفا یکی از محتوای زیر را انتخاب کنید:')
    return '\n'.join(lines)

def _group_twitter_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('➕ متن',  callback_data='grp:add_text'),
           InlineKeyboardButton('➖ متن',  callback_data='grp:del_text'))
    kb.add(InlineKeyboardButton('➕ عکس',  callback_data='grp:add_photo'),
           InlineKeyboardButton('➖ عکس',  callback_data='grp:del_photo'))
    kb.add(InlineKeyboardButton('🔀 انتقال محتوا', callback_data='grp:transfer_twitter'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data='grp:back'))
    return kb

def _group_instagram_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('➕ ریلز',   callback_data='grp:add_reel'),
           InlineKeyboardButton('➖ ریلز',   callback_data='grp:del_reel'))
    kb.add(InlineKeyboardButton('➕ استوری', callback_data='grp:add_story'),
           InlineKeyboardButton('➖ استوری', callback_data='grp:del_story'))
    kb.add(InlineKeyboardButton('🔀 انتقال محتوا', callback_data='grp:transfer_instagram'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data='grp:back'))
    return kb

def _group_ht_select_kb(prefix: str, back_to: str = 'grp:back'):
    kb = InlineKeyboardMarkup(row_width=1)
    for ht in db.get_all_hashtags():
        p = '🏷' if ht.get('append_tag', 1) else '📁'
        kb.add(InlineKeyboardButton(f'{p} {ht["name"]}',
                                    callback_data=f'{prefix}:{ht["id"]}'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data=back_to))
    return kb

def _group_no_tag_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for g in db.get_no_tag_groups():
        tc = db.count_texts_by_hashtag(g['id'])
        kb.add(InlineKeyboardButton(f'📁 {g["name"]} ({tc} متن)',
                                    callback_data=f'grp:no_tag_info:{g["id"]}'))
    kb.add(InlineKeyboardButton('➕ اضافه کردن گروه', callback_data='grp:add_no_tag'))
    kb.add(InlineKeyboardButton('➖ حذف گروه',         callback_data='grp:del_no_tag_list'))
    kb.add(InlineKeyboardButton('⬅️ برگشت',            callback_data='grp:back'))
    return kb

def _group_transfer_kb(domain: str):
    back_to = 'grp:twitter' if domain == 'twitter' else 'grp:instagram'
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton('📋 کپی',     callback_data=f'grp:transfer:{domain}:copy'),
           InlineKeyboardButton('✂️ برداشتن', callback_data=f'grp:transfer:{domain}:cut'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data=back_to))
    return kb

def _group_transfer_type_kb(domain: str, mode: str):
    back_to = f'grp:transfer_{domain}'
    kb = InlineKeyboardMarkup(row_width=1)
    if domain == 'twitter':
        kb.add(InlineKeyboardButton('📝 متن',       callback_data=f'grp:tr_type:{domain}:{mode}:text'))
        kb.add(InlineKeyboardButton('🖼 عکس',       callback_data=f'grp:tr_type:{domain}:{mode}:photo'))
        kb.add(InlineKeyboardButton('📦 همه محتوا', callback_data=f'grp:tr_type:{domain}:{mode}:all'))
    else:
        kb.add(InlineKeyboardButton('🎬 ریلز',      callback_data=f'grp:tr_type:{domain}:{mode}:reel'))
        kb.add(InlineKeyboardButton('⭕️ استوری',    callback_data=f'grp:tr_type:{domain}:{mode}:story'))
        kb.add(InlineKeyboardButton('📦 همه محتوا', callback_data=f'grp:tr_type:{domain}:{mode}:all_ig'))
    kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data=back_to))
    return kb

# ─────────────────────────────────────────────────────────────────────────────
# Text builders
# ─────────────────────────────────────────────────────────────────────────────
