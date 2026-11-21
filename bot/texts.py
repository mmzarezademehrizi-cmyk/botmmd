# -*- coding: utf-8 -*-
"""سازنده‌های متن پیام‌های پنل‌های مختلف (بدون ارسال، فقط ساخت رشته)."""
import html as _html

from base import database as db
from base.core import (
    S_WAIT_WELCOME_MSG, S_WAIT_TWITTER_WELCOME_MSG, S_WAIT_INSTAGRAM_WELCOME_MSG,
    S_WAIT_START_OP_MSG, S_WAIT_END_OP_MSG, S_WAIT_LOCK_MSG, S_WAIT_ADMIN_CONTACT,
    S_WAIT_FLOOD_MSG, S_WAIT_QUICK_ACCESS_MSG, S_WAIT_GUIDE_MSG,
)

# رجیستری پیام‌های قابل‌ویرایش — برای فلوی «اول ببین چیه، بعد بگو تغییرش بده».
# هر ورودی: label (اسم فارسی)، key (کلید ذخیره در zone_settings)، default
# (مقدار پیش‌فرض وقتی چیزی تنظیم نشده)، state (وضعیت انتظار متن جدید)، hint
# (توضیح متغیرهای قابل استفاده، اگه داشته باشه).
MSG_FIELDS = {
    'welcome': {
        'label': 'پیام خوش‌آمدگویی', 'key': 'welcome_msg',
        'default': 'سلام {name} عزیز!\nبه ربات خوش آمدید.',
        'state': S_WAIT_WELCOME_MSG, 'hint': 'متغیر {name} با نام کاربر جایگزین می‌شود.',
    },
    'twitter_welcome': {
        'label': 'پیام خوش‌آمد پنل توییتر', 'key': 'twitter_welcome_msg',
        'default': '', 'state': S_WAIT_TWITTER_WELCOME_MSG, 'hint': '',
    },
    'instagram_welcome': {
        'label': 'پیام خوش‌آمد پنل اینستاگرام', 'key': 'instagram_welcome_msg',
        'default': '', 'state': S_WAIT_INSTAGRAM_WELCOME_MSG, 'hint': '',
    },
    'start_op': {
        'label': 'پیام شروع عملیات', 'key': 'start_op_msg',
        'default': '🚀 عملیات شروع شد!\nهشتگ: {hashtag}',
        'state': S_WAIT_START_OP_MSG, 'hint': 'متغیر {hashtag} با نام هشتگ جایگزین می‌شود.',
    },
    'end_op': {
        'label': 'پیام پایان عملیات', 'key': 'end_op_msg',
        'default': 'پایان عملیات {hashtag}',
        'state': S_WAIT_END_OP_MSG, 'hint': 'متغیر {hashtag} با نام هشتگ جایگزین می‌شود.',
    },
    'lock': {
        'label': 'پیام قفل 🔒', 'key': 'lock_msg',
        'default': '🚫 دسترسی موقت مسدود شد\n⏳ زمان باقی‌مانده: {time}',
        'state': S_WAIT_LOCK_MSG, 'hint': 'متغیر {time} با زمان باقی‌مانده جایگزین می‌شود.',
    },
    'contact': {
        'label': 'ارتباط با ادمین', 'key': 'admin_contact',
        'default': 'ادمین ربات', 'state': S_WAIT_ADMIN_CONTACT, 'hint': '',
    },
    'flood': {
        'label': 'پیام کاربر در حال اذیت کردن ربات', 'key': 'flood_block_msg',
        'default': '', 'state': S_WAIT_FLOOD_MSG, 'hint': '',
    },
    'quick_access': {
        'label': 'پیام دسترسی سریع ⚡️', 'key': 'quick_access_msg',
        'default': 'برای دریافت سریع محتوا از دکمه‌های زیر استفاده کنید',
        'state': S_WAIT_QUICK_ACCESS_MSG, 'hint': '',
    },
    'guide': {
        'label': '📖 راهنما', 'key': 'guide_msg',
        'default': 'راهنمای استفاده از ربات هنوز توسط ادمین تنظیم نشده.',
        'state': S_WAIT_GUIDE_MSG, 'hint': '',
    },
}

def get_msg_field(key):
    return MSG_FIELDS.get(key)

def get_msg_field_by_state(state):
    for key, field in MSG_FIELDS.items():
        if field['state'] == state:
            return key, field
    return None, None

def _account_text(panel_user=None):
    if panel_user:
        zone = db.get_zone(panel_user['zone_id'])
        zname = zone['name'] if zone else 'نامشخص'
        return (
            '🔐 <b>حساب کاربری</b>\n\n'
            f'✅ وارد شده‌اید.\n'
            f'یوزرنیم: <b>{_html.escape(panel_user["username"])}</b>\n'
            f'ناحیه: <b>{_html.escape(zname)}</b>'
        )
    return (
        '🔐 <b>حساب کاربری</b>\n\n'
        'برای ورود، ابتدا باید ثبت‌نام کرده باشید. اگر حساب دارید روی «ورود» بزنید.'
    )

def _zones_admin_text():
    zones = db.get_all_zones()
    guest_state = '✅ فعال' if db.is_guest_login_enabled() else '❌ غیرفعال'
    guest_zone = db.get_zone(db.get_guest_zone_id()) if db.get_guest_zone_id() else None
    guest_line = f'\n\n👤 ورود مهمان: {guest_state}' + (f' (ناحیه: {_html.escape(guest_zone["name"])})' if guest_zone else '')
    if not zones:
        return '📁 <b>مدیریت ناحیه‌ها</b>\n\nهنوز هیچ ناحیه‌ای ثبت نشده. با دکمه‌ی زیر یکی اضافه کنید.' + guest_line
    lines = ['📁 <b>مدیریت ناحیه‌ها</b>\n\nروی هر ناحیه بزنید تا لیست کاربرانش را ببینید:' + guest_line]
    return '\n'.join(lines)

def _zone_detail_text(zone):
    users = db.get_panel_users_by_zone(zone['id'])
    lines = [f'📁 <b>ناحیه: {_html.escape(zone["name"])}</b>\n']
    if db.get_guest_zone_id() == zone['id']:
        lines.append('📌 این ناحیه، ناحیه‌ی مهمان‌هاست.\n')
    if not users:
        lines.append('هیچ کاربری در این ناحیه ثبت‌نام نکرده است.')
    else:
        lines.append(f'👥 {len(users)} کاربر — برای جزئیات هرکدام روی نامش بزنید:')
    return '\n'.join(lines)

_SERVICE_LABELS = {'app': '📱 اپ', 'bot': '🤖 بات', 'site': '🌐 سایت'}

def _services_line(services: set) -> str:
    return '، '.join(_SERVICE_LABELS[k] for k in ('app', 'bot', 'site') if k in services) or 'هیچ‌کدام'

def _zone_services_text(zone, current: set) -> str:
    return (
        f'🔧 <b>دسترسیِ سرویسِ ناحیه‌ی «{_html.escape(zone["name"])}»</b>\n\n'
        f'کاربرهایِ این ناحیه (که خودشون override ندارن) الان به این سرویس‌ها دسترسی دارن:\n'
        f'{_services_line(current)}\n\n'
        'با زدنِ هرکدوم روشن/خاموشش کن:'
    )

def _puser_services_text(user, effective: set, has_override: bool) -> str:
    src = 'override شخصیِ خودش' if has_override else 'ارثِ ناحیه'
    return (
        f'🔧 <b>دسترسیِ سرویسِ «{_html.escape(user["username"])}»</b>\n\n'
        f'الان (منبع: {src}):\n{_services_line(effective)}\n\n'
        'با زدنِ هرکدوم روشن/خاموشش کن (این خودکار override شخصی می‌سازه):'
    )

def _commander_zones_text(pu) -> str:
    zone_ids = db.get_commander_zone_ids(pu['id'])
    if not zone_ids:
        return '🎖 <b>پنل فرمانده</b>\n\nهنوز هیچ ناحیه‌ای زیرِ فرماندهیِ شما نیست.'
    return f'🎖 <b>پنل فرمانده</b>\n\nناحیه‌هایی که زیرِ فرماندهیِ شمان ({len(zone_ids)} تا):'

def _commander_zone_detail_text(zone, pu) -> str:
    users = db.get_panel_users_by_zone(zone['id'])
    limit = db.get_commander_creation_limit(pu['id'])
    limit_line = 'نامحدود' if limit is None else f'{limit} نفر'
    lines = [
        f'📁 <b>ناحیه: {_html.escape(zone["name"])}</b>',
        f'سقفِ ساختِ کاربرِ شما در کل: {limit_line}',
        '',
    ]
    lines.append('هیچ کاربری هنوز نیست.' if not users else f'👥 {len(users)} کاربر:')
    return '\n'.join(lines)

def _commander_puser_detail_text(user, zone_name: str, show_password: bool) -> str:
    if show_password:
        pw_line = f'پسورد: <code>{_html.escape(user.get("password_plain") or "")}</code>'
    else:
        pw_line = '🔒 مجوزِ دیدنِ پسورد را ندارید.'
    return (
        f'👤 <b>{_html.escape(user["username"])}</b>\n\n'
        f'ناحیه: <b>{_html.escape(zone_name)}</b>\n'
        f'{pw_line}\n'
        f'تاریخ ثبت‌نام: {user["created_at"]}'
    )

def _panel_user_detail_text(user, zone_name: str, show_password: bool = False):
    tg = f'<code>{user["telegram_user_id"]}</code>' if user.get('telegram_user_id') else 'هنوز وارد نشده'
    last_login = user.get('last_login_at') or 'هرگز'
    if show_password:
        pw_line = f'پسورد: <code>{_html.escape(user.get("password_plain") or "")}</code>'
    else:
        pw_line = '🔒 فقط مالک ربات می‌تواند پسورد را ببیند.'
    return (
        f'👤 <b>{_html.escape(user["username"])}</b>\n\n'
        f'ناحیه: <b>{_html.escape(zone_name)}</b>\n'
        f'{pw_line}\n'
        f'آیدی تلگرام (آخرین ورود): {tg}\n'
        f'تاریخ ثبت‌نام: {user["created_at"]}\n'
        f'آخرین ورود: {last_login}'
    )

def _people_list_text():
    sups = db.get_all_supervisors()
    if not sups:
        return '👥 <b>افراد (سرپرست‌ها)</b>\n\nهنوز هیچ سرپرستی تعیین نشده.'
    lines = ['👥 <b>افراد (سرپرست‌ها)</b>\n']
    for s in sups:
        zone_lbl = '، '.join(z['name'] for z in s['zones'])
        lines.append(f'• {_html.escape(s["username"])} ← {_html.escape(zone_lbl)}')
    return '\n'.join(lines)

def _people_zone_select_text(username):
    return (
        f'👤 <b>{_html.escape(username)}</b>\n\n'
        'روی هر ناحیه بزنید تا دسترسی سرپرستی‌اش فعال/غیرفعال بشه (✅=فعال، ❌=غیرفعال)، '
        'بعد «تایید و ذخیره» رو بزنید:'
    )

def _supervised_users_text(zone_name, users):
    if not users:
        return f'📁 <b>{_html.escape(zone_name)}</b>\n\nهیچ کاربری در این ناحیه نیست.'
    lines = [f'📁 <b>{_html.escape(zone_name)}</b>\n']
    for u in users:
        lines.append(f'👤 {_html.escape(u["username"])} — پسورد: <code>{_html.escape(u.get("password_plain") or "")}</code>')
    return '\n'.join(lines)

def _ht_zone_select_text(ht_text, selected_count, total_zones):
    kind_hint = 'برای همه‌ی ناحیه‌ها' if selected_count == 0 else f'برای {selected_count} ناحیه از {total_zones} ناحیه'
    return (
        f'📁 <b>{_html.escape(ht_text)}</b>\n\n'
        'روی هر ناحیه بزنید تا فعال/غیرفعال بشه (✅=فعال، ❌=غیرفعال). '
        'اگه هیچ‌کدوم رو تیک نزنید، یعنی این محتوا برای همه‌ی ناحیه‌ها فعال می‌شه.\n\n'
        f'وضعیت فعلی: <b>{kind_hint}</b>'
    )

def _settings_main_text():
    return (
        f'📊 تعداد متن‌های موجود در ربات: <b>{db.count_texts()}</b> عدد\n\n'
        'دستورات مدیریتی را از کلیدهای زیر انتخاب کنید:'
    )

def _status_text():
    op      = db.is_operation_active()
    active  = db.get_active_hashtags()
    ht_lbl  = ' | '.join(_html.escape(h['name']) for h in active) if active else 'هیچ‌کدام'
    stats   = db.get_hashtag_stats()
    lines = [
        '📈 <b>وضعیت فعلی ربات:</b>',
        f'وضعیت عملیات: {"فعال ✅" if op else "غیرفعال 🔴"}',
        f'هشتگ‌های فعال: {ht_lbl}',
        f'محدودیت: {db.get_text_allowance()} متن / {db.get_cooldown_hours()} ساعت',
        '', '🗂️ <b>موجودی هشتگ‌ها:</b>',
    ]
    for s in (stats or []):
        am = ' ✅' if any(h['id'] == s['id'] for h in active) else ''
        lines.append(f'- {_html.escape(s["name"])}{am} &#8594; متن: {s["text_count"]} | عکس: {s["photo_count"]}')
    if not stats:
        lines.append('هیچ هشتگی ثبت نشده است.')
    return '\n'.join(lines)

def _limit_text(zone_name=None):
    hdr = f'⚙️ <b>محدودیت‌ها — ناحیه: {_html.escape(zone_name)}</b>\n\n' if zone_name else '⚙️ <b>محدودیت‌ها</b>\n\n'
    return hdr + 'لطفا بخش مورد نظر را انتخاب کنید:'

def _limit_twitter_text(zone_id=None):
    return (
        f'⚙️ <b>محدودیت محتوای توییتر</b>\n'
        f'• سقف متن: <b>{db.get_text_allowance(zone_id)}</b> تا\n'
        f'• مدت قفل: <b>{db.get_cooldown_hours(zone_id)}</b> ساعت\n\n'
        'کدام مورد را تغییر می‌دهید؟'
    )

def _limit_instagram_text(zone_id=None):
    return (
        f'⚙️ <b>محدودیت محتوای اینستاگرام</b>\n'
        f'• سقف ریلز: <b>{db.get_reel_limit(zone_id)}</b> تا (هر <b>{db.get_reel_cooldown_hours(zone_id)}</b> ساعت)\n'
        f'• سقف استوری: <b>{db.get_story_limit(zone_id)}</b> تا (هر <b>{db.get_story_cooldown_hours(zone_id)}</b> ساعت)\n\n'
        'کدام بخش را تغییر می‌دهید؟'
    )

def _limit_reel_text(zone_id=None):
    return (
        f'🎬 <b>محدودیت ریلز</b>\n'
        f'• تعداد دریافت ریلز: <b>{db.get_reel_limit(zone_id)}</b> تا\n'
        f'• محدودیت ساعت: <b>{db.get_reel_cooldown_hours(zone_id)}</b> ساعت\n\n'
        'کدام مورد را تغییر می‌دهید؟'
    )

def _limit_story_text(zone_id=None):
    return (
        f'⭕️ <b>محدودیت استوری</b>\n'
        f'• تعداد دریافت استوری: <b>{db.get_story_limit(zone_id)}</b> تا\n'
        f'• محدودیت ساعت: <b>{db.get_story_cooldown_hours(zone_id)}</b> ساعت\n\n'
        'کدام مورد را تغییر می‌دهید؟'
    )

def _groups_text():
    groups = db.get_all_groups()
    if not groups:
        return 'ربات در هیچ گروهی نیست.'
    return '\n'.join(f'{i}_ {g["group_name"]} . {g.get("group_link","N/A")} . {g["group_id"]}'
                     for i, g in enumerate(groups, 1))

def _panel_ref(telegram_user_id, fallback_first_name=None):
    """نمایش یوزرنیم پنلی مرتبط با این آیدی تلگرام (نه یوزرنیم تلگرام)،
    وگرنه اسم یا آیدی به‌عنوان جایگزین."""
    pu = db.get_panel_user_by_telegram_id(telegram_user_id)
    if pu:
        return _html.escape(pu['username'])
    if fallback_first_name:
        return _html.escape(fallback_first_name)
    return f'(ID: {telegram_user_id})'

def _group_admins_text():
    admins = db.get_all_group_admins()
    if not admins:
        return '👥 <b>ادمین‌های گروه:</b>\nهیچ ادمین گروهی وجود ندارد.'
    lines = ['👥 <b>ادمین‌های گروه:</b>']
    for a in admins:
        lines.append(f'• {_panel_ref(a["user_id"], a.get("first_name"))}')
    return '\n'.join(lines)

def _bot_admins_text():
    admins = db.get_all_bot_admins()
    if not admins:
        return '👤 هیچ ادمین ربات‌ای وجود ندارد.'
    lines = ['👤 <b>ادمین‌های ربات:</b>']
    for a in admins:
        lines.append(f'• {_panel_ref(a["user_id"], a.get("first_name"))}')
    return '\n'.join(lines)

def _vip_text():
    vips = db.get_all_vip_users()
    hdr  = '👑 VIP توییتر\n\nلیست کاربران VIP فعلی:'
    if not vips:
        return hdr + '\nهیچ کاربر ویژه‌ای ثبت نشده است.'
    lines = [hdr]
    for v in vips:
        lines.append(f'• 👑 {_panel_ref(v["user_id"], v.get("first_name"))}')
    return '\n'.join(lines)

def _instagram_vip_text():
    vips = db.get_all_instagram_vip_users()
    hdr  = '👑 VIP اینستاگرام\n\nلیست کاربران VIP فعلی:'
    if not vips:
        return hdr + '\nهیچ کاربر ویژه‌ای ثبت نشده است.'
    lines = [hdr]
    for v in vips:
        lines.append(f'• 👑 {_panel_ref(v["user_id"], v.get("first_name"))}')
    return '\n'.join(lines)

def _website_text():
    url    = db.get_website_url() or '(تنظیم نشده)'
    status = '✅ فعال' if db.get_website_status() else '❌ غیر فعال'
    return (
        f'🌐 <b>مدیریت وب سایت</b>\n\n'
        f'لینک فعلی: <code>{_html.escape(url)}</code>\n'
        f'وضعیت: {status}\n\nوب سایت را تغییر دهید:'
    )

def _msg_settings_text(zone_name=None):
    hdr = f'📝 مدیریت پیام‌های ربات — ناحیه: {_html.escape(zone_name)}\n' if zone_name else '📝 بخش مدیریت پیام‌های ربات\n'
    return hdr + 'گزینه مورد نظر را انتخاب کنید:'

def _hashtag_access_text():
    op      = db.is_operation_active()
    hts     = db.get_all_hashtags()
    if not hts:
        return '🏷️ هیچ هشتگی ثبت نشده است.'
    active   = [h for h in hts if h.get('is_active')]
    inactive = [h for h in hts if not h.get('is_active')]
    lines = []
    if op:
        if active:
            lines.append('✅ <b>فعال:</b>')
            for h in active:
                p = '🏷' if h.get('append_tag', 1) else '📁'
                lines.append(f'  {p} {_html.escape(h["name"])} ({db.count_texts_by_hashtag(h["id"])} متن)')
        if inactive:
            lines.append('\n❌ <b>غیرفعال:</b>')
            for h in inactive:
                p = '🏷' if h.get('append_tag', 1) else '📁'
                lines.append(f'  {p} {_html.escape(h["name"])} ({db.count_texts_by_hashtag(h["id"])} متن)')
    else:
        lines.append('📋 <b>همه هشتگ‌ها:</b>')
        for h in hts:
            p = '🏷' if h.get('append_tag', 1) else '📁'
            lines.append(f'  {p} {_html.escape(h["name"])} ({db.count_texts_by_hashtag(h["id"])} متن)')
    lines.append('\nبرای تغییر وضعیت روی دکمه کلیک کنید:')
    return '\n'.join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# Panel edit helper
# ─────────────────────────────────────────────────────────────────────────────
def _admin_status_text():
    if not db.get_all_hashtags():
        return 'هشتگی پیدا نشد'
    if not db.is_operation_active():
        return f'عملیات غیر فعال\nتعداد متن : {db.count_texts()} تا'
    active = db.get_active_hashtags()
    total  = db.count_active_texts()
    if len(active) <= 1:
        return f'تعداد متن فعال: {total}'
    return f'تعداد متن از {len(active)} تا هشتگ : {total}'

