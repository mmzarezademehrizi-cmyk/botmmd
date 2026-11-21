# -*- coding: utf-8 -*-
"""تحویل محتوا به کاربر: متن، عکس (دسته‌ای)، پیام خوش‌آمد، وضعیت کاربر."""
import time
import html as _html
from datetime import datetime
from urllib.parse import quote
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo

from base import database as db
from base.core import bot, is_owner, is_bot_admin_or_owner, format_wait_time
from bot.keyboards import user_main_menu, _user_ht_select_kb, _quick_access_kb, _user_ht_photo_kb, account_menu_kb, login_required_kb
from bot.admin_ops import update_all_admin_status_messages

def _require_panel_login(uid, cid):
    """
    دروازه‌ی ورود اجباری قبل از دریافت محتوا: ادمین/مالک بدون نیاز به حساب
    پنل عبور می‌کند (zone_id=None یعنی همه‌ی هشتگ‌های فعال، صرف‌نظر از
    ناحیه — رفتار قبلی/سراسری). بقیه‌ی کاربران باید حتما با پنل ثبت‌نام/ورود
    کرده باشند؛ وگرنه پیام راهنما نشان داده می‌شود و None برمی‌گردد.
    """
    if is_bot_admin_or_owner(uid):
        return {'zone_id': None}
    pu = db.get_panel_user_by_telegram_id(uid)
    if not pu:
        bot.send_message(cid,
            '🔐 برای دریافت محتوا ابتدا باید وارد حساب کاربری خود شوید.\n'
            'از دکمه‌ی «🔐 حساب کاربری» در منوی اصلی استفاده کنید.',
            reply_markup=account_menu_kb(logged_in=False))
        return None
    return pu

def send_welcome(chat_id, first_name):
    name = first_name or 'کاربر'
    pu = db.get_panel_user_by_telegram_id(chat_id)
    if not is_bot_admin_or_owner(chat_id) and not pu:
        bot.send_message(chat_id,
            '🔐 لطفا ابتدا وارد حساب کاربری خود شوید.',
            reply_markup=login_required_kb())
        return
    zone_id = None if is_bot_admin_or_owner(chat_id) else db.get_user_zone_id(chat_id)
    welcome = db.get_welcome_msg(zone_id).replace('{name}', name)
    supervisor = bool(pu) and db.is_supervisor(pu['id'])
    commander  = bool(pu) and db.is_commander(pu['id'])
    bot.send_message(chat_id, welcome, reply_markup=user_main_menu(supervisor=supervisor, commander=commander), parse_mode='HTML')
    if db.is_operation_active() and db.is_quick_access_enabled():
        quick_msg = db.get_zone_setting(zone_id, 'quick_access_msg', 'برای دریافت سریع محتوا از دکمه‌های زیر استفاده کنید')
        bot.send_message(chat_id, quick_msg, reply_markup=_quick_access_kb())

def _send_photo_smart(cid, photo_row):
    """
    بر اساس media_type ذخیره‌شده می‌فرسته؛ اگر تلگرام خطای «نوع فایل اشتباهه»
    داد (که معمولاً به‌خاطر دیتای قدیمیه — قبل از اینکه ستون media_type اضافه
    بشه، همه چیز 'photo' فرض می‌شد)، خودش نوع مخالف رو امتحان می‌کنه و رکورد
    دیتابیس رو هم اصلاح می‌کنه تا دفعه‌ی بعد این اتفاق نیفته.
    """
    is_video = photo_row.get('media_type') == 'video'
    try:
        if is_video:
            bot.send_video(cid, photo_row['file_id'])
        else:
            bot.send_photo(cid, photo_row['file_id'])
    except Exception as e:
        msg = str(e)
        if 'as Photo' in msg or 'as Video' in msg or 'wrong file identifier' in msg.lower():
            corrected = 'photo' if is_video else 'video'
            if corrected == 'video':
                bot.send_video(cid, photo_row['file_id'])
            else:
                bot.send_photo(cid, photo_row['file_id'])
            db.fix_photo_media_type(photo_row['id'], corrected)
        else:
            raise

def _deliver_photos_batch(uid, cid, hid, batch_size: int = 10, panel_user_id=None):
    """
    این تابع تا ۱۰ عکس را همزمان (به‌صورت آلبوم) می‌فرستد؛ اگر کمتر از ۱۰ تا
    موجود بود، همان تعداد موجود. اگر مخزن این هشتگ از اول خالی بود، پیام
    «چرخه دوباره» گفته نمی‌شود — آن پیام فقط زمانی می‌آید که کاربر واقعاً
    همه‌چیز را قبلاً گرفته و تمام کرده.

    panel_user_id: idِ پنلیِ فرستنده (نه آیدیِ تلگرام) - فقط برایِ ثبتِ
    content_history با همون قراردادی که web_app.py استفاده می‌کنه (منفیِ
    idِ پنلی، تا با idِ واقعیِ تلگرام - که همیشه مثبته - تداخل نکنه).
    None یعنی کاربر ادمین/مالکِ باته (حساب پنلی نداره)، که این‌ها اصلاً
    ثبت نمی‌شن (تحلیلِ رفتار برای دوستان معنی داره، نه تستِ خودِ مالک).
    """
    total = db.count_photos_by_hashtag(hid)
    if total == 0:
        bot.send_message(cid, 'متاسفانه داخل بنده عکسی نیست')
        return
    batch = db.get_unreceived_photos_batch(uid, hid, limit=batch_size)
    if not batch:
        bot.send_message(cid,
            'شما تمامی عکس‌های این هشتگ را دریافت کرده‌اید. '
            'چرخه مجدداً از ابتدا آغاز می‌شود 🔄')
        db.reset_user_photos_for_hashtag(uid, hid)
        batch = db.get_unreceived_photos_batch(uid, hid, limit=batch_size)
    if not batch:
        return
    if len(batch) == 1:
        _send_photo_smart(cid, batch[0])
    else:
        try:
            media = [
                InputMediaVideo(p['file_id']) if p.get('media_type') == 'video' else InputMediaPhoto(p['file_id'])
                for p in batch
            ]
            bot.send_media_group(cid, media)
        except Exception as e:
            msg = str(e)
            if 'as Photo' in msg or 'as Video' in msg or 'wrong file identifier' in msg.lower():
                # حداقل یکی از آیتم‌های این دسته media_type اشتباهی دارد — به‌جای
                # آلبوم، یکی‌یکی با خودترمیمی می‌فرستیم تا کاربر چیزی از دست نده.
                for p in batch:
                    _send_photo_smart(cid, p)
            else:
                raise
    for p in batch:
        db.mark_photo_received(uid, p['id'])
        if panel_user_id is not None:
            db.add_content_history(
                -panel_user_id, "photo", hashtag_id=hid,
                media_type=p.get('media_type', 'photo'), ref_id=p['id'], platform='bot',
            )

def _deliver_texts_from_hashtag(uid, cid, count, hid, panel_user_id=None):
    if db.count_texts_by_hashtag(hid) == 0:
        bot.send_message(cid, 'متاسفانه داخل بنده متنی نیست')
        return
    fetched = db.pop_texts_with_ids(count, hashtag_id=hid)
    actual  = len(fetched)
    for item in fetched:
        encoded = quote(item['content'], safe='')
        tw_url  = f'https://twitter.com/intent/tweet?text={encoded}'
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('پست در توییتر 🐦', url=tw_url))
        bot.send_message(cid, item['content'], reply_markup=kb)
        if panel_user_id is not None:
            db.add_content_history(-panel_user_id, "text", hashtag_id=hid, text_content=item['content'], platform='bot')
        time.sleep(0.05)
    if not is_bot_admin_or_owner(uid) and not db.is_vip_user(uid):
        db.update_cooldown(uid, actual)
    update_all_admin_status_messages()
    if db.count_active_texts() < 10 and db.get_setting('low_text_alert_sent') != 'true':
        ht = db.get_hashtag_by_id(hid)
        owner_id = db.get_owner_id()
        try:
            if owner_id:
                bot.send_message(owner_id,
                    f'⚠️ <b>هشدار:</b> متن‌های هشتگ {_html.escape(ht["name"] if ht else "؟")} رو به اتمام است!',
                    parse_mode='HTML')
            db.set_setting('low_text_alert_sent', 'true')
        except Exception:
            pass
    if actual < count:
        bot.send_message(cid, 'ربات ته کشید')

def handle_text_request(message, count: int):
    uid = message.from_user.id
    cid = message.chat.id
    if not db.is_operation_active():
        bot.send_message(cid, 'عملیاتی در جریان نیست.')
        return
    pu = _require_panel_login(uid, cid)
    if pu is None:
        return
    zone_id = pu['zone_id']
    if is_bot_admin_or_owner(uid) or db.is_vip_user(uid):
        to_send = count
    else:
        remaining, locked_until = db.check_cooldown(uid, zone_id)
        if remaining <= 0:
            wait_str   = format_wait_time(locked_until) if locked_until else '?'
            allowance  = db.get_text_allowance(zone_id)
            cooldown_h = db.get_cooldown_hours(zone_id)
            lock_tmpl  = db.get_zone_setting(zone_id, 'lock_msg', None) or (
                f'🚫 دسترسی موقت مسدود شد\n\n'
                f'شما به سقف مجاز دریافت {allowance} متن در {cooldown_h} ساعت رسیده‌اید.\n'
                '⏳ زمان باقی‌مانده: {time}'
            )
            bot.send_message(cid, lock_tmpl.replace('{time}', wait_str))
            return
        to_send = min(count, remaining)
    active_hts = db.get_active_hashtags_for_zone(zone_id)
    if not active_hts:
        bot.send_message(cid, 'متاسفانه داخل بنده متنی نیست')
        return
    if len(active_hts) > 1:
        bot.send_message(cid, 'لطفا هشتگ مورد نظر را انتخاب کنید.',
                         reply_markup=_user_ht_select_kb(to_send, zone_id))
        return
    _deliver_texts_from_hashtag(uid, cid, to_send, active_hts[0]['id'], panel_user_id=pu.get('id'))

def handle_photo_request(uid, cid, batch_size: int = 10):
    """مشترک بین دکمه‌ی «دریافت عکس» و دستور سریع «عکس N» و quick-access."""
    if not db.is_operation_active():
        bot.send_message(cid, 'عملیاتی در جریان نیست.')
        return
    pu = _require_panel_login(uid, cid)
    if pu is None:
        return
    zone_id = pu['zone_id']
    active = db.get_active_hashtags_for_zone(zone_id)
    if not active:
        bot.send_message(cid, 'متاسفانه داخل بنده عکسی نیست')
        return
    if len(active) > 1:
        bot.send_message(cid, 'لطفا هشتگ مورد نظر را انتخاب کنید.',
                         reply_markup=_user_ht_photo_kb(zone_id))
        return
    _deliver_photos_batch(uid, cid, active[0]['id'], batch_size=batch_size, panel_user_id=pu.get('id'))

# ─────────────────────────────────────────────────────────────────────────────
# User status
# ─────────────────────────────────────────────────────────────────────────────
def _send_user_status(uid: int, cid: int, panel_label: str = None):
    if is_owner(uid):
        role = '👑 مالک ربات'
        info = '⚡️ محدودیت: ندارید'
    elif db.is_bot_admin(uid):
        role = '🛡 ادمین ربات'
        info = '⚡️ محدودیت: ندارید'
    elif db.is_vip_user(uid):
        role = '⭐️ کاربر VIP'
        info = '⚡️ محدودیت: ندارید'
    else:
        role       = '👤 کاربر عادی'
        zone_id    = db.get_user_zone_id(uid)
        remaining, locked_until = db.check_cooldown(uid, zone_id)
        allowance  = db.get_text_allowance(zone_id)
        received   = allowance - remaining
        if locked_until and datetime.utcnow() < locked_until:
            info = (f'متن دریافت شده: {received} تا\nسقف مجاز: {allowance} تا\n'
                    f'وضعیت: 🔒 قفل\nزمان آزاد شدن: {format_wait_time(locked_until)}')
        else:
            info = (f'متن دریافت شده: {received} تا\n'
                    f'باقی‌مانده: {remaining} تا\nوضعیت: ✅ آزاد')
    header = f'📊 <b>وضعیت شما در {panel_label}:</b>' if panel_label else '📊 <b>وضعیت شما:</b>'
    bot.send_message(cid, f'{header}\n\nنقش: {role}\n{info}', parse_mode='HTML')

# ─────────────────────────────────────────────────────────────────────────────
# Owner helpers
# ─────────────────────────────────────────────────────────────────────────────
