# -*- coding: utf-8 -*-
"""هندلر پیام‌های خصوصی: /start ،/setting ،/status و کل منطق دکمه‌های کاربر/ادمین."""
import time
import re
import io
import html as _html
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from base import database as db
from bot import antiflood
from base.core import (
    bot, log, _safe_handler, _update_activity, _get_user_panel, _switch_panel,
    is_owner, is_bot_admin_or_owner, is_admin_or_owner, is_group_chat,
    get_state, set_state, clear_state, cur_state, state_data, _edit_panel,
    get_admin_zone_ctx,
    set_people_selection, get_people_selection,
    _PRIVATE_ESCAPE_KEYWORDS,
    S_WAIT_GROUP_HASHTAG, S_WAIT_GROUP_CONTENT, S_WAIT_BROADCAST,
    S_WAIT_ADMIN_ID, S_WAIT_BOT_ADMIN_ID, S_WAIT_LIMIT_HOURS, S_WAIT_LIMIT_TEXTS,
    S_WAIT_LIMIT_REEL_COUNT, S_WAIT_LIMIT_REEL_HOURS,
    S_WAIT_LIMIT_STORY_COUNT, S_WAIT_LIMIT_STORY_HOURS,
    S_WAIT_WEBSITE_URL, S_WAIT_WELCOME_MSG, S_WAIT_TWITTER_WELCOME_MSG,
    S_WAIT_INSTAGRAM_WELCOME_MSG, S_WAIT_START_OP_MSG, S_WAIT_END_OP_MSG,
    S_WAIT_VIP_ID, S_WAIT_INSTAGRAM_VIP_ID, S_WAIT_ADMIN_CONTACT, S_WAIT_LOCK_MSG,
    S_WAIT_FLOOD_MSG, S_WAIT_QUICK_ACCESS_MSG, S_WAIT_GUIDE_MSG,
    S_WAIT_PU_LOGIN_USERNAME, S_WAIT_PU_LOGIN_PASSWORD, S_WAIT_ZONE_NAME,
    S_WAIT_OWNER_LOGIN_USERNAME, S_WAIT_OWNER_LOGIN_PASSWORD, S_WAIT_OWNER_LINK_CODE,
    S_WAIT_ADMIN_PU_ZONE, S_WAIT_ADMIN_PU_USERNAME, S_WAIT_ADMIN_PU_PASSWORD,
    S_WAIT_ADMIN_XLSX_FILE, S_WAIT_ADMIN_XLSX_ZONE_PICK, S_WAIT_ADMIN_BULK_COUNT,
    S_WAIT_PEOPLE_USERNAME, S_WAIT_CMD_PU_USERNAME, S_WAIT_CMD_PU_PASSWORD,
    S_WAIT_CMD_ZONE_NAME, commander_pu,
)
from bot.keyboards import (
    user_main_menu, twitter_panel_menu, instagram_panel_menu,
    owner_settings_keyboard, _limit_kb, _bot_admins_kb, _hashtag_toggle_kb,
    _user_ht_photo_kb, _group_admins_kb, _vip_twitter_kb, _instagram_vip_kb,
    account_menu_kb, owner_zones_kb, zone_detail_kb, login_required_kb,
    username_candidates_kb, people_zone_select_kb, supervisor_zones_kb,
    zone_pick_kb, commander_zones_kb,
)
from features import excel_tools
from bot.texts import (
    _settings_main_text, _status_text, _limit_text, _groups_text,
    _bot_admins_text, _hashtag_access_text, _msg_settings_text,
    _vip_text, _instagram_vip_text, _account_text, _group_admins_text,
    _people_zone_select_text, _supervised_users_text, _commander_zones_text,
)
from bot.content_delivery import (
    handle_text_request, handle_photo_request, _deliver_photos_batch, send_welcome, _send_user_status,
)
from bot.instagram_delivery import (
    handle_reel_request, handle_story_request, _send_instagram_status,
)
from bot.admin_ops import (
    _owner_start_operation, _owner_stop_operation, _owner_backup,
    _set_admin_commands, update_admin_status_msg,
)
from bot.handlers_group import _send_group_panel

@bot.message_handler(commands=['start'], func=lambda m: m.chat.type == 'private')
@_safe_handler
def handle_start_cmd(message):
    uid = message.from_user.id
    cid = message.chat.id
    _update_activity(uid)
    db.register_user(uid, message.from_user.username,
                     message.from_user.first_name, message.from_user.last_name)
    # فازِ ۶۳: لینکِ «رفتن به بات» از اپ (/start link_<token>) - تأییدِ ورود بدونِ پسورد
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) == 2 and not is_group_chat(message.chat.type):
        from bot import bot_link
        if bot_link.handle_start_payload(message, parts[1].strip()):
            return
    if is_group_chat(message.chat.type):
        if is_admin_or_owner(uid):
            _send_group_panel(cid)
        return
    send_welcome(cid, message.from_user.first_name)

@bot.message_handler(commands=['text'], func=lambda m: m.chat.type == 'private')
@_safe_handler
def handle_text_cmd(message):
    _update_activity(message.from_user.id)
    handle_text_request(message, 1)

@bot.message_handler(commands=['reels'], func=lambda m: m.chat.type == 'private')
@_safe_handler
def handle_reels_cmd(message):
    _update_activity(message.from_user.id)
    handle_reel_request(message, 1)

@bot.message_handler(commands=['setting'])
@_safe_handler
def handle_setting_cmd(message):
    uid = message.from_user.id
    cid = message.chat.id
    if not is_bot_admin_or_owner(uid):
        return
    bot.send_message(cid, _settings_main_text(), parse_mode='HTML',
                     reply_markup=owner_settings_keyboard())

@bot.message_handler(commands=['status'])
def handle_status_cmd(message):
    uid = message.from_user.id
    cid = message.chat.id
    if not is_bot_admin_or_owner(uid):
        return
    bot.send_message(cid, _status_text(), parse_mode='HTML')

# ─────────────────────────────────────────────────────────────────────────────
# ورود مالک (یوزرنیم/پسورد همون چیزیه که توی سایت ساخته شده - مستقل از یوزرنیم تلگرام)
# ─────────────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=['ownerlogin'], func=lambda m: m.chat.type == 'private')
@_safe_handler
def handle_owner_login_cmd(message):
    uid = message.from_user.id
    cid = message.chat.id
    login_id = f'owner_tg:{uid}'
    allowed, locked_until = db.check_login_lock(login_id)
    if not allowed:
        bot.send_message(cid,
            f'🚫 به‌خاطر تلاش‌های ناموفق پیاپی، ورود مالک موقتاً قفل شده.\n'
            f'⏳ تا {locked_until} صبر کنید.')
        return
    set_state(uid, cid, S_WAIT_OWNER_LOGIN_USERNAME)
    bot.send_message(cid, '👤 یوزرنیم مالک را وارد کنید:')

# ─────────────────────────────────────────────────────────────────────────────
# ورود مالک با کد یک‌بارمصرف (پیشنهادی - از تب «حساب مالک» توی سایت گرفته می‌شه؛
# دیگه نیازی به تایپ یوزرنیم/پسورد و ریسک اشتباه تایپی نیست)
# ─────────────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=['linkowner'], func=lambda m: m.chat.type == 'private')
@_safe_handler
def handle_owner_link_cmd(message):
    uid = message.from_user.id
    cid = message.chat.id
    login_id = f'owner_tg:{uid}'
    allowed, locked_until = db.check_login_lock(login_id)
    if not allowed:
        bot.send_message(cid,
            f'🚫 به‌خاطر تلاش‌های ناموفق پیاپی، ورود مالک موقتاً قفل شده.\n'
            f'⏳ تا {locked_until} صبر کنید.')
        return
    bot.send_message(cid,
        'ℹ️ این ربات مستقله (بدونِ سایت). مالک با آیدیِ عددیِ تلگرام تعیین می‌شه:\n'
        'آیدیِ تو: <code>%s</code>\n'
        'اون رو توی فایلِ <code>.owner_id</code> کنارِ main.py بنویس و ربات رو ریستارت کن.' % uid,
        parse_mode='HTML')

# ─────────────────────────────────────────────────────────────────────────────
# جستجوی یوزرنیم برای افزودن ادمین/VIP (به‌جای آیدی عددی)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_username_lookup(uid, cid, text, action, apply_fn, success_render):
    """
    text: یوزرنیم پنلی‌ای که ادمین وارد کرده (همون یوزرنیمی که خودِ ادمین
    موقع ساخت کاربر پنل تعیین کرده — نه یوزرنیم تلگرام).
    action: شناسه‌ی کوتاه برای callback_data (مثلا 'add_vip').
    apply_fn(target_telegram_id, panel_username, first_name): افزودن واقعی.
    success_render() -> (متن HTML, کیبورد) برای نمایش بعد از موفقیت.
    """
    prompt_mid = state_data(uid, cid).get('prompt_mid')
    candidates = db.find_panel_users_by_username(text)
    if not candidates:
        bot.send_message(cid,
            '❌ کاربر پنلی با این یوزرنیم پیدا نشد. یوزرنیم دیگری وارد کنید '
            '(یا اول از «پنل کاربران» بسازش):')
        return
    if len(candidates) == 1:
        c = candidates[0]
        if not c.get('telegram_user_id'):
            bot.send_message(cid,
                f'⚠️ کاربر «{c["username"]}» هنوز از تو ربات وارد نشده (باید یک‌بار /start بزنه و '
                'با «🔐 ورود به حساب» وارد بشه)، تا بشه بهش این نقش رو داد. یوزرنیم دیگری امتحان کن یا بعداً دوباره تلاش کن:')
            return
        clear_state(uid, cid)
        fn_row = db.get_user(c['telegram_user_id'])
        first_name = fn_row.get('first_name') if fn_row else None
        apply_fn(c['telegram_user_id'], c['username'], first_name)
        body, kb = success_render()
        if prompt_mid:
            try:
                _edit_panel(cid, prompt_mid, body, kb, parse_mode='HTML')
                return
            except Exception:
                pass
        bot.send_message(cid, f'✅ {c["username"]} اضافه شد.')
        return
    msg = '🔎 چند یوزرنیم شبیه به این پیدا شد؛ شبیه‌ترین اول اومده — مورد نظر را انتخاب کنید:'
    kb  = username_candidates_kb(candidates, action)
    if prompt_mid:
        try:
            _edit_panel(cid, prompt_mid, msg, kb)
            return
        except Exception:
            pass
    bot.send_message(cid, msg, reply_markup=kb)


# ─────────────────────────────────────────────────────────────────────────────
# ایمپورتِ دسته‌ایِ کاربر از فایلِ اکسل (فازِ ۴)
# ─────────────────────────────────────────────────────────────────────────────
def _handle_admin_xlsx_upload(message):
    """وقتی ادمین/مالک تویِ state=S_WAIT_ADMIN_XLSX_FILE یه سند بفرسته.
    فایل دانلود، پارس، و جفت‌هایِ یوزرنیم/پسورد تویِ state_data نگه
    داشته می‌شن تا مرحله‌ی بعد (انتخابِ ناحیه با دکمه) که واقعاً ساخته
    بشن - این‌جوری اگه ادمین بین این دو مرحله منصرف بشه، هیچی تویِ
    دیتابیس نمی‌شینه."""
    uid, cid = message.from_user.id, message.chat.id
    doc = message.document
    fname = (doc.file_name or '').lower()
    if not fname.endswith('.xlsx'):
        bot.send_message(cid, '⚠️ فقط فایلِ .xlsx قبول می‌شه. دوباره بفرست یا /cancel بزن.')
        return
    try:
        file_info = bot.get_file(doc.file_id)
        raw = bot.download_file(file_info.file_path)
    except Exception:
        log.exception('xlsx download failed')
        bot.send_message(cid, '⚠️ دانلودِ فایل از تلگرام با خطا مواجه شد. دوباره امتحان کن.')
        return
    try:
        pairs = excel_tools.parse_users_xlsx(raw)
    except excel_tools.XlsxParseError as e:
        bot.send_message(cid, f'⚠️ {e}')
        return
    except Exception:
        log.exception('xlsx parse failed')
        bot.send_message(cid, '⚠️ خوندنِ فایل با خطایی غیرمنتظره مواجه شد.')
        return

    zones = db.get_all_zones()
    if not zones:
        clear_state(uid, cid)
        bot.send_message(cid, '⚠️ هنوز هیچ ناحیه‌ای نساختی؛ اول یه ناحیه بساز.')
        return
    set_state(uid, cid, S_WAIT_ADMIN_XLSX_ZONE_PICK, pairs=pairs)
    bot.send_message(
        cid,
        f'📊 {len(pairs)} ردیف تو فایل پیدا شد.\nاین کاربرها عضوِ کدام ناحیه باشند؟',
        reply_markup=zone_pick_kb(prefix='admin_xlsx_zone_pick'),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Private message handler
# ─────────────────────────────────────────────────────────────────────────────
@bot.message_handler(
    func=lambda m: m.chat.type == 'private',
    content_types=['text', 'photo', 'video', 'document', 'voice',
                   'audio', 'sticker', 'video_note', 'animation']
)
@_safe_handler
def handle_private(message):
    uid  = message.from_user.id
    cid  = message.chat.id

    # ── آنتی‌فلود: باید همیشه اولین چک باشد ──────────────────────────────────
    if not is_bot_admin_or_owner(uid):
        if antiflood.check_and_handle(message):
            return

    text = (message.text or '').strip()
    # نسخه‌ی HTML همون متن، با حفظ بولد/ایتالیک/و غیره — برای ذخیره‌ی پیام‌های
    # قابل‌ویرایش (خوش‌آمد، پنل‌ها، و غیره) استفاده می‌شود تا فرمت‌بندی از بین
    # نرود. برای دکمه‌های ساده‌ی منو (بدون فرمت) این دقیقاً برابر با `text` است.
    text_html = (getattr(message, 'html_text', None) or text).strip()
    _update_activity(uid)
    db.register_user(uid, message.from_user.username,
                     message.from_user.first_name, message.from_user.last_name)

    # ── escape از state ────────────────────────────────────────────────────
    _PU_STATES = (
        S_WAIT_PU_LOGIN_USERNAME, S_WAIT_PU_LOGIN_PASSWORD,
        S_WAIT_OWNER_LOGIN_USERNAME, S_WAIT_OWNER_LOGIN_PASSWORD,
    )
    if cur_state(uid, cid) in _PU_STATES:
        esc = _PRIVATE_ESCAPE_KEYWORDS - {'1','2','3','4','5','6','7','8'}
        if text.startswith('/') or text in esc:
            clear_state(uid, cid)
    if cur_state(uid, cid) and is_bot_admin_or_owner(uid):
        esc = _PRIVATE_ESCAPE_KEYWORDS - {'1','2','3','4','5','6','7','8'}
        if text.startswith('/') or text in esc:
            clear_state(uid, cid)

    cs = cur_state(uid, cid)

    # broadcast
    if is_owner(uid) and cs == S_WAIT_BROADCAST:
        clear_state(uid, cid)
        users        = db.get_all_users()
        sent = failed = 0
        for u in users:
            try:
                bot.copy_message(u['user_id'], cid, message.message_id)
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        bot.send_message(cid, f'پیام برای {sent} نفر ارسال شد. ({failed} خطا)')
        return

    # states
    def _handle_state():
        if cs == S_WAIT_ADMIN_ID and is_owner(uid):
            def _apply(t, un, fn):
                db.add_group_admin(t, un, fn)
            def _render():
                return _group_admins_text(), _group_admins_kb()
            _handle_username_lookup(uid, cid, text, 'add_admin', _apply, _render)
            return True
        if cs == S_WAIT_LIMIT_HOURS and is_bot_admin_or_owner(uid):
            if text.isdigit() and int(text) > 0:
                db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'user_cooldown_hours', text); clear_state(uid, cid)
                bot.send_message(cid, f'✅ محدودیت به {text} ساعت تغییر یافت.')
            else:
                bot.send_message(cid, 'لطفاً یک عدد صحیح مثبت وارد کنید.')
            return True
        if cs == S_WAIT_LIMIT_TEXTS and is_bot_admin_or_owner(uid):
            if text.isdigit() and int(text) > 0:
                db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'user_text_allowance', text); clear_state(uid, cid)
                bot.send_message(cid, f'✅ محدودیت به {text} متن تغییر یافت.')
            else:
                bot.send_message(cid, 'لطفاً یک عدد صحیح مثبت وارد کنید.')
            return True
        if cs == S_WAIT_BOT_ADMIN_ID and is_owner(uid):
            def _apply(t, un, fn):
                db.add_bot_admin(t, un, fn)
                update_admin_status_msg(t)
                _set_admin_commands(t)
            def _render():
                return _bot_admins_text(), _bot_admins_kb()
            _handle_username_lookup(uid, cid, text, 'add_bot_admin', _apply, _render)
            return True
        if cs == S_WAIT_VIP_ID and is_owner(uid):
            def _apply(t, un, fn):
                db.add_vip_user(t, un, fn)
            def _render():
                return _vip_text(), _vip_twitter_kb()
            _handle_username_lookup(uid, cid, text, 'add_vip', _apply, _render)
            return True
        if cs == S_WAIT_INSTAGRAM_VIP_ID and is_owner(uid):
            def _apply(t, un, fn):
                db.add_instagram_vip_user(t, un, fn)
            def _render():
                return _instagram_vip_text(), _instagram_vip_kb()
            _handle_username_lookup(uid, cid, text, 'add_ig_vip', _apply, _render)
            return True
        if cs == S_WAIT_LIMIT_REEL_COUNT and is_bot_admin_or_owner(uid):
            if text.isdigit() and int(text) > 0:
                db.set_reel_limit(int(text), get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
                bot.send_message(cid, f'✅ تعداد دریافت ریلز به {text} تا تغییر یافت.')
            else:
                bot.send_message(cid, 'لطفاً یک عدد صحیح مثبت وارد کنید.')
            return True
        if cs == S_WAIT_LIMIT_REEL_HOURS and is_bot_admin_or_owner(uid):
            if text.isdigit() and int(text) > 0:
                db.set_reel_cooldown_hours(int(text), get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
                bot.send_message(cid, f'✅ محدودیت ساعت ریلز به {text} ساعت تغییر یافت.')
            else:
                bot.send_message(cid, 'لطفاً یک عدد صحیح مثبت وارد کنید.')
            return True
        if cs == S_WAIT_LIMIT_STORY_COUNT and is_bot_admin_or_owner(uid):
            if text.isdigit() and int(text) > 0:
                db.set_story_limit(int(text), get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
                bot.send_message(cid, f'✅ تعداد دریافت استوری به {text} تا تغییر یافت.')
            else:
                bot.send_message(cid, 'لطفاً یک عدد صحیح مثبت وارد کنید.')
            return True
        if cs == S_WAIT_LIMIT_STORY_HOURS and is_bot_admin_or_owner(uid):
            if text.isdigit() and int(text) > 0:
                db.set_story_cooldown_hours(int(text), get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
                bot.send_message(cid, f'✅ محدودیت ساعت استوری به {text} ساعت تغییر یافت.')
            else:
                bot.send_message(cid, 'لطفاً یک عدد صحیح مثبت وارد کنید.')
            return True
        if cs == S_WAIT_WELCOME_MSG and is_bot_admin_or_owner(uid):
            db.set_welcome_msg(text_html, get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام خوش‌آمدگویی تغییر یافت.')
            return True
        if cs == S_WAIT_TWITTER_WELCOME_MSG and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'twitter_welcome_msg', text_html); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام خوش‌آمد پنل توییتر تغییر یافت.')
            return True
        if cs == S_WAIT_INSTAGRAM_WELCOME_MSG and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'instagram_welcome_msg', text_html); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام خوش‌آمد پنل اینستاگرام تغییر یافت.')
            return True
        if cs == S_WAIT_START_OP_MSG and is_bot_admin_or_owner(uid):
            db.set_start_op_msg(text, get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام شروع عملیات تغییر یافت.')
            return True
        if cs == S_WAIT_END_OP_MSG and is_bot_admin_or_owner(uid):
            db.set_end_op_msg(text, get_admin_zone_ctx(uid, cid)); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام پایان عملیات تغییر یافت.')
            return True
        if cs == S_WAIT_LOCK_MSG and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'lock_msg', text); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام قفل تغییر یافت.\nمتغیر {time} با زمان واقعی جایگزین می‌شود.')
            return True
        if cs == S_WAIT_ADMIN_CONTACT and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'admin_contact', text_html); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام ارتباط با ادمین تغییر یافت.')
            return True
        if cs == S_WAIT_FLOOD_MSG and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'flood_block_msg', text_html); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام کاربر در حال اذیت کردن ربات تغییر یافت.')
            return True
        if cs == S_WAIT_QUICK_ACCESS_MSG and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'quick_access_msg', text_html); clear_state(uid, cid)
            bot.send_message(cid, '✅ پیام دسترسی سریع تغییر یافت.')
            return True
        if cs == S_WAIT_GUIDE_MSG and is_bot_admin_or_owner(uid):
            db.set_zone_setting(get_admin_zone_ctx(uid, cid), 'guide_msg', text_html); clear_state(uid, cid)
            bot.send_message(cid, '✅ راهنما تغییر یافت.')
            return True
        if cs == S_WAIT_WEBSITE_URL and is_bot_admin_or_owner(uid):
            if text.startswith(('http://', 'https://')):
                db.set_website_url(text); clear_state(uid, cid)
                bot.send_message(cid, f'✅ لینک وب سایت به‌روز شد:\n{text}')
            else:
                bot.send_message(cid, '⚠️ لینک باید با http:// یا https:// شروع شود.')
            return True
        # ── ورود به پنل ─────────────────────────────────────────────────
        if cs == S_WAIT_PU_LOGIN_USERNAME:
            set_state(uid, cid, S_WAIT_PU_LOGIN_PASSWORD, username=text.strip())
            bot.send_message(cid, '🔑 پسورد را وارد کنید:')
            return True
        if cs == S_WAIT_PU_LOGIN_PASSWORD:
            username = state_data(uid, cid).get('username')
            clear_state(uid, cid)
            login_id = f'tg:{uid}'
            allowed, locked_until = db.check_login_lock(login_id)
            if not allowed:
                bot.send_message(cid,
                    f'🚫 به‌خاطر تلاش‌های ناموفق پیاپی، ورود موقتاً قفل شده.\n'
                    f'⏳ تا {locked_until} صبر کنید.',
                    reply_markup=login_required_kb())
                return True
            result = db.verify_panel_login(username, text)
            if not result:
                attempts, locked_until = db.record_failed_login(login_id)
                remaining = db.LOGIN_MAX_ATTEMPTS - attempts
                if locked_until:
                    bot.send_message(cid,
                        f'❌ یوزرنیم یا پسورد اشتباه است.\n🚫 به‌خاطر تلاش‌های زیاد، ورود تا {locked_until} قفل شد.',
                        reply_markup=login_required_kb())
                else:
                    bot.send_message(cid,
                        f'❌ یوزرنیم یا پسورد اشتباه است. ({remaining} تلاش دیگر باقی‌مانده)',
                        reply_markup=login_required_kb())
                return True
            db.record_successful_login(login_id)
            db.mark_panel_login(result['id'], uid)
            bot.send_message(cid, f'✅ خوش آمدید {message.from_user.first_name}!',
                             reply_markup=user_main_menu(supervisor=db.is_supervisor(result['id']),
                                                          commander=db.is_commander(result['id'])))
            return True
        # ── ورود مالک (یوزرنیم/پسورد سایت) ─────────────────────────────
        if cs == S_WAIT_OWNER_LOGIN_USERNAME:
            set_state(uid, cid, S_WAIT_OWNER_LOGIN_PASSWORD, username=text.strip())
            bot.send_message(cid, '🔑 پسورد مالک را وارد کنید:')
            return True
        if cs == S_WAIT_OWNER_LOGIN_PASSWORD:
            username = state_data(uid, cid).get('username')
            clear_state(uid, cid)
            login_id = f'owner_tg:{uid}'
            allowed, locked_until = db.check_login_lock(login_id)
            if not allowed:
                bot.send_message(cid,
                    f'🚫 به‌خاطر تلاش‌های ناموفق پیاپی، ورود مالک موقتاً قفل شده.\n'
                    f'⏳ تا {locked_until} صبر کنید.')
                return True
            ok = db.try_owner_login(uid, username, text)
            if not ok:
                attempts, locked_until = db.record_failed_login(login_id)
                remaining = db.LOGIN_MAX_ATTEMPTS - attempts
                if locked_until:
                    bot.send_message(cid,
                        f'❌ یوزرنیم یا پسورد اشتباه است.\n🚫 به‌خاطر تلاش‌های زیاد، ورود مالک تا {locked_until} قفل شد.')
                else:
                    bot.send_message(cid,
                        f'❌ یوزرنیم یا پسورد اشتباه است. ({remaining} تلاش دیگر باقی‌مانده)')
                return True
            db.record_successful_login(login_id)
            _set_admin_commands(uid)
            bot.send_message(cid,
                f'✅ به‌عنوان مالک ربات شناخته شدید، {message.from_user.first_name}!',
                reply_markup=owner_settings_keyboard())
            return True
        if cs == S_WAIT_OWNER_LINK_CODE:
            clear_state(uid, cid)
            login_id = f'owner_tg:{uid}'
            allowed, locked_until = db.check_login_lock(login_id)
            if not allowed:
                bot.send_message(cid,
                    f'🚫 به‌خاطر تلاش‌های ناموفق پیاپی، ورود مالک موقتاً قفل شده.\n'
                    f'⏳ تا {locked_until} صبر کنید.')
                return True
            ok = db.try_owner_link_code(uid, text.strip())
            if not ok:
                attempts, locked_until = db.record_failed_login(login_id)
                remaining = db.LOGIN_MAX_ATTEMPTS - attempts
                if locked_until:
                    bot.send_message(cid,
                        f'❌ کد اشتباهه یا منقضی شده.\n🚫 به‌خاطر تلاش‌های زیاد، ورود مالک تا {locked_until} قفل شد.')
                else:
                    bot.send_message(cid,
                        f'❌ کد اشتباهه یا منقضی شده. یه کد تازه از تب «حساب مالک» توی سایت بگیر. '
                        f'({remaining} تلاش دیگر باقی‌مانده)')
                return True
            db.record_successful_login(login_id)
            _set_admin_commands(uid)
            bot.send_message(cid,
                f'✅ به‌عنوان مالک ربات شناخته شدید، {message.from_user.first_name}!',
                reply_markup=owner_settings_keyboard())
            return True
        # ── افزودن سرپرست (افراد) توسط مالک ─────────────────────────────
        if cs == S_WAIT_PEOPLE_USERNAME and is_owner(uid):
            prompt_mid = state_data(uid, cid).get('prompt_mid')
            target = db.get_panel_user_by_username(text.strip())
            if not target:
                bot.send_message(cid, '⚠️ کاربر پنلی با این یوزرنیم پیدا نشد. یوزرنیم دیگری وارد کن (یا اول از «پنل کاربران» بسازش):')
                return True
            clear_state(uid, cid)
            set_people_selection(uid, cid, target['id'], db.get_supervisor_zone_ids(target['id']))
            body = _people_zone_select_text(target['username'])
            kb = people_zone_select_kb(db.get_supervisor_zone_ids(target['id']), target['id'])
            if prompt_mid:
                try:
                    _edit_panel(cid, prompt_mid, body, kb, parse_mode='HTML')
                    return True
                except Exception:
                    pass
            bot.send_message(cid, body, parse_mode='HTML', reply_markup=kb)
            return True
        # ── افزودن کاربر پنل توسط ادمین ─────────────────────────────────
        if cs == S_WAIT_ADMIN_PU_USERNAME and is_bot_admin_or_owner(uid):
            uname = text.strip()
            if not re.fullmatch(r'[A-Za-z0-9_]{3,32}', uname):
                bot.send_message(cid, '⚠️ یوزرنیم باید ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، عدد و _ باشد. دوباره وارد کنید:')
                return True
            if db.panel_username_exists(uname):
                bot.send_message(cid, '⚠️ این یوزرنیم قبلاً گرفته شده. یوزرنیم دیگری وارد کنید:')
                return True
            zid = state_data(uid, cid).get('zone_id')
            set_state(uid, cid, S_WAIT_ADMIN_PU_PASSWORD, username=uname, zone_id=zid)
            bot.send_message(cid, '🔑 پسورد این کاربر را وارد کنید (حداقل ۴ کاراکتر):')
            return True
        if cs == S_WAIT_ADMIN_PU_PASSWORD and is_bot_admin_or_owner(uid):
            if len(text) < 4:
                bot.send_message(cid, '⚠️ پسورد باید حداقل ۴ کاراکتر باشد. دوباره وارد کنید:')
                return True
            sd = state_data(uid, cid)
            uname, zid = sd.get('username'), sd.get('zone_id')
            clear_state(uid, cid)
            zone = db.get_zone(zid)
            if not zone or db.panel_username_exists(uname):
                bot.send_message(cid, '⚠️ خطا رخ داد (ناحیه پیدا نشد یا یوزرنیم تکراری شد). دوباره تلاش کنید.')
                return True
            db.create_panel_user(uname, text, zid)
            bot.send_message(cid,
                f'✅ کاربر ساخته شد.\nیوزرنیم: <code>{_html.escape(uname)}</code>\nپسورد: <code>{_html.escape(text)}</code>\nناحیه: {_html.escape(zone["name"])}\n\n'
                'این اطلاعات را برای کاربر ارسال کنید تا با آن‌ها وارد شود.',
                parse_mode='HTML')
            return True
        # ── مدیریت ناحیه‌ها (ادمین) ────────────────────────────────────
        if cs == S_WAIT_ADMIN_BULK_COUNT and is_bot_admin_or_owner(uid):
            if not (text.isdigit() and 1 <= int(text) <= 500):
                bot.send_message(cid, '⚠️ یک عدد صحیح بین ۱ تا ۵۰۰ وارد کنید:')
                return True
            zid = state_data(uid, cid).get('zone_id')
            clear_state(uid, cid)
            zone = db.get_zone(zid)
            if not zone:
                bot.send_message(cid, '⚠️ این ناحیه دیگر وجود ندارد.')
                return True
            count = int(text)
            created = db.bulk_create_panel_users(zid, count, created_by=None)
            data = excel_tools.build_new_users_xlsx(created, zone["name"])
            from telebot.types import InputFile
            bot.send_document(
                cid, InputFile(io.BytesIO(data), filename=f'users_{zone["name"]}.xlsx'),
                caption=f'✅ {count} کاربرِ رندوم برایِ ناحیه‌ی «{_html.escape(zone["name"])}» ساخته شد.',
            )
            return True
        # ── فازِ ۸: افزودنِ کاربر / ساختِ ناحیه توسطِ فرمانده ──────────────
        if cs == S_WAIT_CMD_PU_USERNAME:
            cmd = commander_pu(uid)
            if not cmd:
                clear_state(uid, cid); return True
            uname = text.strip()
            if not re.fullmatch(r'[A-Za-z0-9_]{3,32}', uname):
                bot.send_message(cid, '⚠️ یوزرنیم باید ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، عدد و _ باشد. دوباره وارد کنید:')
                return True
            if db.panel_username_exists(uname):
                bot.send_message(cid, '⚠️ این یوزرنیم قبلاً گرفته شده. یوزرنیم دیگری وارد کنید:')
                return True
            zid = state_data(uid, cid).get('zone_id')
            set_state(uid, cid, S_WAIT_CMD_PU_PASSWORD, username=uname, zone_id=zid)
            bot.send_message(cid, '🔑 پسورد این کاربر را وارد کنید (حداقل ۴ کاراکتر):')
            return True
        if cs == S_WAIT_CMD_PU_PASSWORD:
            cmd = commander_pu(uid)
            if not cmd:
                clear_state(uid, cid); return True
            if len(text) < 4:
                bot.send_message(cid, '⚠️ پسورد باید حداقل ۴ کاراکتر باشد. دوباره وارد کنید:')
                return True
            sd = state_data(uid, cid)
            uname, zid = sd.get('username'), sd.get('zone_id')
            clear_state(uid, cid)
            zone = db.get_zone(zid)
            if (not zone or db.panel_username_exists(uname)
                    or not db.commander_can_manage_zone(cmd['id'], zid)
                    or not db.commander_has_permission(cmd['id'], 'user.add')
                    or not db.commander_can_create_users(cmd['id'])):
                bot.send_message(cid, '⚠️ دیگر امکانِ ساختِ این کاربر نیست (دسترسی/سقف/ناحیه). دوباره از منو تلاش کنید.')
                return True
            db.create_panel_user(uname, text, zid, created_by=cmd['id'])
            bot.send_message(cid,
                f'✅ کاربر ساخته شد.\nیوزرنیم: <code>{_html.escape(uname)}</code>\nپسورد: <code>{_html.escape(text)}</code>\nناحیه: {_html.escape(zone["name"])}',
                parse_mode='HTML')
            return True
        if cs == S_WAIT_CMD_ZONE_NAME:
            cmd = commander_pu(uid)
            if not cmd or not db.commander_has_permission(cmd['id'], 'zone.create'):
                clear_state(uid, cid); return True
            zname = text.strip()
            if not zname:
                bot.send_message(cid, '⚠️ نام نامعتبر بود.'); return True
            if db.zone_name_exists(zname):
                bot.send_message(cid, '⚠️ ناحیه‌ای با این نام قبلاً وجود دارد. نام دیگری وارد کنید:')
                return True
            clear_state(uid, cid)
            new_zid = db.add_zone(zname)
            zone_ids = db.get_commander_zone_ids(cmd['id']) + [new_zid]
            db.set_commander(cmd['id'], zone_ids, list(db.get_commander_permissions(cmd['id'])))
            bot.send_message(cid, f'✅ ناحیه‌ی «{_html.escape(zname)}» ساخته شد و زیرِ فرماندهیِ شما اضافه شد.', parse_mode='HTML')
            return True
        if cs == S_WAIT_ZONE_NAME and is_bot_admin_or_owner(uid):
            zname = text.strip()
            prompt_mid = state_data(uid, cid).get('prompt_mid')
            if not zname:
                bot.send_message(cid, '⚠️ نام ناحیه نمی‌تواند خالی باشد. دوباره وارد کنید:')
                return True
            if db.zone_name_exists(zname):
                bot.send_message(cid, '⚠️ ناحیه‌ای با این نام قبلاً وجود دارد. نام دیگری وارد کنید:')
                return True
            clear_state(uid, cid)
            db.add_zone(zname)
            if prompt_mid:
                try:
                    _edit_panel(cid, prompt_mid, f'📁 ناحیه‌ی «{_html.escape(zname)}» اضافه شد.', owner_zones_kb())
                    return True
                except Exception:
                    pass
            bot.send_message(cid, f'✅ ناحیه‌ی «{zname}» اضافه شد.')
            return True
        return False

    if message.content_type != 'text':
        if (message.content_type == 'document' and cur_state(uid, cid) == S_WAIT_ADMIN_XLSX_FILE
                and is_bot_admin_or_owner(uid)):
            _handle_admin_xlsx_upload(message)
            return
        if not is_owner(uid):
            send_welcome(cid, message.from_user.first_name)
        return

    if _handle_state():
        return

    # ── دکمه‌های ادمین ───────────────────────────────────────────────────
    if is_bot_admin_or_owner(uid):
        if text == 'تنظیمات':
            bot.send_message(cid, _settings_main_text(), parse_mode='HTML',
                             reply_markup=owner_settings_keyboard()); return
        if text == 'شروع عملیات':  _owner_start_operation(cid); return
        if text == 'پایان عملیات': _owner_stop_operation(cid); return
        if text == 'گروه ها':      bot.send_message(cid, _groups_text()); return
        if text == 'پشتیبان گیری': _owner_backup(cid); return
        if text == 'وضعیت':        bot.send_message(cid, _status_text(), parse_mode='HTML'); return
        if text == 'محدودیت':
            bot.send_message(cid, _limit_text(), parse_mode='HTML', reply_markup=_limit_kb()); return
    if is_owner(uid):
        if text == 'پیام':
            set_state(uid, cid, S_WAIT_BROADCAST)
            bot.send_message(cid, 'پیام خود را وارد کنید:'); return
        if text == 'ادمین':
            bot.send_message(cid, _bot_admins_text(), parse_mode='HTML',
                             reply_markup=_bot_admins_kb()); return

    # ── سوییچ به پنل‌ها از منوی اصلی ─────────────────────────────────────────
    if text == 'محتوای توییتر 🐦':
        zone_id = None if is_bot_admin_or_owner(uid) else db.get_user_zone_id(uid)
        welcome = db.get_zone_setting(zone_id, 'twitter_welcome_msg', '')
        _switch_panel(uid, cid, 'twitter', welcome, twitter_panel_menu(),
                     parse_mode='HTML', user_msg_id=message.message_id)
        return
    if text == 'محتوای اینستاگرام 📸':
        zone_id = None if is_bot_admin_or_owner(uid) else db.get_user_zone_id(uid)
        welcome = db.get_zone_setting(zone_id, 'instagram_welcome_msg', '')
        _switch_panel(uid, cid, 'instagram', welcome, instagram_panel_menu(),
                     parse_mode='HTML', user_msg_id=message.message_id)
        return
    if text == 'بازگشت به صفحه اصلی':
        name    = message.from_user.first_name or 'کاربر'
        pu      = db.get_panel_user_by_telegram_id(uid)
        zone_id = None if is_bot_admin_or_owner(uid) else db.get_user_zone_id(uid)
        welcome = db.get_welcome_msg(zone_id).replace('{name}', name)
        supervisor = bool(pu) and db.is_supervisor(pu['id'])
        commander  = bool(pu) and db.is_commander(pu['id'])
        _switch_panel(uid, cid, 'main', welcome, user_main_menu(supervisor=supervisor, commander=commander),
                     parse_mode='HTML', user_msg_id=message.message_id)
        return

    # ── دکمه‌های پنل توییتر ──────────────────────────────────────────────────
    if text == 'دریافت متن':
        handle_text_request(message, 1); return
    if text == 'دریافت عکس':
        handle_photo_request(uid, cid); return

    # ── دکمه‌های پنل اینستاگرام ───────────────────────────────────────────────
    if text == 'دریافت ریلز':
        handle_reel_request(message); return
    if text == 'دریافت استوری':
        handle_story_request(message); return

    # ── دستور سریع «نوع‌محتوا + عدد» مثل «متن 5» یا «ریلز 2» ─────────────────
    m = re.match(r'^(متن|عکس|ریلز|استوری)\s+(\d+)$', text)
    if m:
        kind, count = m.group(1), max(1, int(m.group(2)))
        if kind == 'متن':
            max_allowed = db.get_text_allowance()
            if count > max_allowed and not (is_bot_admin_or_owner(uid) or db.is_vip_user(uid)):
                bot.send_message(cid, f'محدودیت تا {max_allowed} تا هست'); return
            handle_text_request(message, count); return
        if kind == 'عکس':
            handle_photo_request(uid, cid, batch_size=min(count, 10)); return
        if kind == 'ریلز':
            max_allowed = db.get_reel_limit()
            if count > max_allowed and not (is_bot_admin_or_owner(uid) or db.is_instagram_vip_user(uid)):
                bot.send_message(cid, f'محدودیت تا {max_allowed} تا هست'); return
            handle_reel_request(message, count); return
        if kind == 'استوری':
            max_allowed = db.get_story_limit()
            if count > max_allowed and not (is_bot_admin_or_owner(uid) or db.is_instagram_vip_user(uid)):
                bot.send_message(cid, f'محدودیت تا {max_allowed} تا هست'); return
            handle_story_request(message, count); return

    # ── هشتگ چیست؟ (مشترک بین پنل توییتر و اینستاگرام) ──────────────────────
    if text == 'هشتگ چیست؟':
        if not db.is_operation_active():
            bot.send_message(cid, 'عملیاتی در جریان نیست.'); return
        active = db.get_active_hashtags()
        if not active:
            bot.send_message(cid, 'هیچ هشتگی فعال نیست.'); return
        bot.send_message(cid, '🏷️ هشتگ ' + ' و '.join(h['name'] for h in active)); return

    # ── وضعیت من (بسته به این‌که کاربر توی کدوم پنل باشد فرق می‌کند) ─────────
    if text == '📊 وضعیت من':
        panel = _get_user_panel(uid)
        if panel == 'twitter':
            _send_user_status(uid, cid, 'پنل محتوای توییتر')
        elif panel == 'instagram':
            _send_instagram_status(uid, cid)
        else:
            # توی منوی اصلی، هر دو وضعیت با هم نشون داده می‌شن
            _send_user_status(uid, cid, 'پنل محتوای توییتر')
            _send_instagram_status(uid, cid)
        return

    if text in {'دکمه دسترسی هشتگ متن', 'دسترسی هشتگ متن'}:
        if not is_bot_admin_or_owner(uid): return
        bot.send_message(cid, _hashtag_access_text(), parse_mode='HTML',
                         reply_markup=_hashtag_toggle_kb()); return
    if text == 'وب سایت':
        url = db.get_website_url()
        if not db.get_website_status() or not url:
            send_welcome(cid, message.from_user.first_name); return
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('🌐 باز کردن وب سایت', url=url))
        bot.send_message(cid, 'برای ورود به وب سایت روی دکمه زیر کلیک کنید:', reply_markup=kb); return
    if text in {'ارتباط با ادمین', '📞 ارتباط با ادمین'}:
        zone_id = None if is_bot_admin_or_owner(uid) else db.get_user_zone_id(uid)
        bot.send_message(cid, db.get_zone_setting(zone_id, 'admin_contact', 'ادمین ربات'), parse_mode='HTML'); return
    if text == '🔐 ورود به حساب':
        set_state(uid, cid, S_WAIT_PU_LOGIN_USERNAME)
        bot.send_message(cid, '🔓 یوزرنیم خود را وارد کنید:'); return
    if text == '👤 ورود مهمان':
        if not db.is_guest_login_enabled():
            bot.send_message(cid, '⚠️ ورود مهمان غیرفعال است.'); return
        result = db.create_guest_login(uid)
        if not result:
            bot.send_message(cid, '⚠️ فعلاً ناحیه‌ی مهمان تنظیم نشده، به ادمین اطلاع بده.'); return
        bot.send_message(cid, f'✅ به‌صورت مهمان وارد شدید، {message.from_user.first_name}!',
                         reply_markup=user_main_menu(supervisor=db.is_supervisor(result['id']),
                                                      commander=db.is_commander(result['id'])))
        return
    if text == '👁 افراد تحت من':
        pu = db.get_panel_user_by_telegram_id(uid)
        if not pu or not db.is_supervisor(pu['id']):
            bot.send_message(cid, 'شما سرپرست هیچ ناحیه‌ای نیستید.'); return
        bot.send_message(cid, '📁 ناحیه‌هایی که سرپرستشون هستی:', reply_markup=supervisor_zones_kb(pu['id'])); return
    if text == '🎖 پنل فرمانده':
        cmd = commander_pu(uid)
        if not cmd:
            bot.send_message(cid, 'شما فرمانده نیستید.'); return
        bot.send_message(cid, _commander_zones_text(cmd), parse_mode='HTML',
                         reply_markup=commander_zones_kb(cmd['id'])); return
    if text == '📖 راهنما':
        zone_id = None if is_bot_admin_or_owner(uid) else db.get_user_zone_id(uid)
        guide = db.get_zone_setting(zone_id, 'guide_msg', 'راهنمای استفاده از ربات هنوز توسط ادمین تنظیم نشده.')
        bot.send_message(cid, guide, parse_mode='HTML'); return
    if text == '🔐 حساب کاربری':
        pu = db.get_panel_user_by_telegram_id(uid)
        bot.send_message(cid, _account_text(pu), parse_mode='HTML',
                         reply_markup=account_menu_kb(logged_in=bool(pu))); return
    send_welcome(cid, message.from_user.first_name)

# ─────────────────────────────────────────────────────────────────────────────
# Group message handler
# ─────────────────────────────────────────────────────────────────────────────
