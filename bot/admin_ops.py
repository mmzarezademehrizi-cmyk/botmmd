# -*- coding: utf-8 -*-
"""عملیات ادمین/مالک: بروزرسانی پیام وضعیت، گزارش به مالک، شروع/پایان عملیات، بک‌آپ."""
from base.paths import ROOT
import io
import os
import time
import zipfile
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from telebot import types
import html as _html

from base import database as db
from features import notifications
from base.core import bot, log
from bot.texts import _admin_status_text
from bot.keyboards import _hashtag_start_op_kb

log = logging.getLogger(__name__)

def update_admin_status_msg(uid: int):
    text = _admin_status_text()
    key  = f'status_msg_{uid}'
    mid_str = db.get_setting(key)
    if mid_str:
        try:
            bot.edit_message_text(text, uid, int(mid_str))
            return
        except Exception as e:
            if 'message is not modified' in str(e):
                return
            # FIX: حذف پیام قدیمی قبل از ساخت جدید
            try:
                bot.delete_message(uid, int(mid_str))
            except Exception:
                pass
            db.set_setting(key, '')
    try:
        msg = bot.send_message(uid, text)
        bot.pin_chat_message(uid, msg.message_id, disable_notification=True)
        db.set_setting(key, str(msg.message_id))
    except Exception as e:
        log.warning('Status msg failed for %s: %s', uid, e)

def update_all_admin_status_messages():
    owner_id = db.get_owner_id()
    if owner_id:
        update_admin_status_msg(owner_id)
    for a in db.get_all_bot_admins():
        try:
            update_admin_status_msg(a['user_id'])
        except Exception as e:
            log.warning('Status refresh failed %s: %s', a['user_id'], e)

# ─────────────────────────────────────────────────────────────────────────────
# Report to owner
# ─────────────────────────────────────────────────────────────────────────────
def _report_to_owner(text: str):
    owner_id = db.get_owner_id()
    if not owner_id:
        return  # هنوز مالک شناسایی نشده
    try:
        now = datetime.now(ZoneInfo('Asia/Tehran'))
        bot.send_message(owner_id,
            f'📋 <b>گزارش</b>\n{_html.escape(text)}\n⏰ {now.strftime("%H:%M")}',
            parse_mode='HTML')
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Command scope setter
# ─────────────────────────────────────────────────────────────────────────────
def _set_admin_commands(uid: int):
    try:
        bot.set_my_commands(
            [types.BotCommand('start',   'شروع ربات'),
             types.BotCommand('text',    'دریافت سریع متن'),
             types.BotCommand('reels',   'دریافت سریع ریلز'),
             types.BotCommand('setting', 'تنظیمات مدیریت'),
             types.BotCommand('status',  'وضعیت')],
            scope=types.BotCommandScopeChat(chat_id=uid)
        )
    except Exception:
        pass

def _set_user_commands():
    try:
        bot.set_my_commands(
            [types.BotCommand('start', 'شروع ربات'),
             types.BotCommand('text',  'دریافت سریع متن'),
             types.BotCommand('reels', 'دریافت سریع ریلز')],
            scope=types.BotCommandScopeDefault()
        )
    except Exception:
        pass

def _reset_user_commands(uid: int):
    """
    وقتی کسی از ادمینی (ادمین ربات یا ادمین گروه) حذف می‌شود، باید منوی
    دستورات اختصاصی‌اش هم پاک شود؛ وگرنه همچنان /setting و /status را می‌بیند
    چون set_my_commands با scope مخصوص همان چت هنوز فعال است.
    """
    try:
        bot.delete_my_commands(scope=types.BotCommandScopeChat(chat_id=uid))
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Content delivery helpers
# ─────────────────────────────────────────────────────────────────────────────
def _owner_start_operation(cid):
    if not db.get_all_hashtags():
        bot.send_message(cid, '⚠️ هیچ هشتگی ثبت نشده است.')
        return
    bot.send_message(cid, '🚀 هشتگ مورد نظر را انتخاب کنید:',
                     reply_markup=_hashtag_start_op_kb())

def _do_start_operation(cid, hid):
    db.set_hashtag_active(hid, True)
    db.set_operation_active(True)
    db.set_setting('low_text_alert_sent', 'false')
    ht      = db.get_hashtag_by_id(hid)
    name    = ht['name'] if ht else 'نامشخص'
    zone_id = ht['zone_id'] if ht else None
    bot.send_message(cid, f'✅ عملیات شروع شد. هشتگ فعال: {name}')
    tmpl = db.get_start_op_msg(zone_id)
    try:
        notifications.notify_zone('operation_start', zone_id, hashtag=name)
    except Exception as e:
        log.warning('push notify operation_start failed: %s', e)
    if zone_id is None:
        # مهم: اینجا از `get_all_users()` استفاده نمی‌کنیم، چون اون جدول
        # شاملِ هرکسی می‌شه که فقط یه‌بار /start زده - حتی کاربرهایی که
        # هنوز وارد حسابِ پنلی‌شون تویِ بات نشدن و اصلاً معلوم نیست چه
        # دسترسی‌ای دارن. تا وقتی کسی وارد نشده، فقط باید پیامِ «ورود به
        # حساب» رو ببینه، نه پیام‌هایِ عملیاتی/محتوایی که وضعیتش براش
        # هنوز مشخص نیست.
        recipients = [pu['telegram_user_id'] for pu in db.get_all_linked_panel_users() if pu.get('telegram_user_id')]
    else:
        recipients = [pu['telegram_user_id'] for pu in db.get_panel_users_by_zone(zone_id) if pu.get('telegram_user_id')]
    sent = 0
    for user_id in recipients:
        try:
            bot.send_message(user_id, tmpl.replace('{hashtag}', name))
            sent += 1
            time.sleep(0.05)
        except Exception:
            pass
    bot.send_message(cid, f'پیام شروع برای {sent} کاربر ارسال شد.')
    update_all_admin_status_messages()

def _owner_stop_operation(cid):
    active = db.get_active_hashtags()
    lbl    = ' و '.join(h['name'] for h in active) if active else 'نامشخص'
    zone_ids = {h.get('zone_id') for h in active} if active else {None}
    db.deactivate_all_hashtags()
    db.set_operation_active(False)
    bot.send_message(cid, '🛑 عملیات متوقف شد.')
    try:
        for zid in zone_ids:
            notifications.notify_zone('operation_stop', zid, hashtag=lbl)
    except Exception as e:
        log.warning('push notify operation_stop failed: %s', e)
    tmpl  = db.get_end_op_msg()
    # همون منطقِ شروعِ عملیات: فقط کسانی که واقعاً وارد حسابشون شدن
    # (telegram_user_id دارن)، نه هرکسی که فقط /start زده.
    users = db.get_all_linked_panel_users()
    sent  = 0
    for u in users:
        try:
            bot.send_message(u['telegram_user_id'], tmpl.replace('{hashtag}', lbl))
            sent += 1
            time.sleep(0.05)
        except Exception:
            pass
    bot.send_message(cid, f'پیام پایان برای {sent} کاربر ارسال شد.')
    update_all_admin_status_messages()

def _owner_backup(cid):
    bot.send_message(cid, '⏳ در حال آماده‌سازی...')
    buf      = io.BytesIO()
    base_dir = ROOT
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(base_dir):
            if fname.endswith('.py') or fname == 'bot_data.db':
                fp = os.path.join(base_dir, fname)
                if os.path.isfile(fp):
                    zf.write(fp, fname)
        for pkg in ('base', 'bot', 'features', 'ops'):   # پکیج‌هایِ کد
            for dp, dn, fns in os.walk(os.path.join(base_dir, pkg)):
                dn[:] = [x for x in dn if x != '__pycache__']
                for fn in fns:
                    if fn.endswith('.py'):
                        fp = os.path.join(dp, fn)
                        zf.write(fp, os.path.relpath(fp, base_dir).replace(os.sep, '/'))
    buf.seek(0)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    bot.send_document(cid, buf, visible_file_name=f'backup_{ts}.zip',
                      caption='📦 پشتیبان‌گیری کامل شد.')

# ─────────────────────────────────────────────────────────────────────────────
# Group panel
# ─────────────────────────────────────────────────────────────────────────────
