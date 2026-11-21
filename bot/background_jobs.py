# -*- coding: utf-8 -*-
"""جاب‌های پس‌زمینه: نوتیفای کول‌داون، کاربر غیرفعال، بک‌آپ خودکار، تایم‌اوت گروه.

فازِ ادامه (بهبودِ عملکرد): این ۴ تا قبلاً هرکدوم Threadِ جداگونه‌ی
خودشون بودن با `while True: ... time.sleep(N)`. الان همه (به‌همراهِ
بک‌آپِ روزانه که از قبل همین‌جوری بود) به‌صورتِ جاب‌هایِ interval روی
همون یک BackgroundScheduler (تویِ main.py) ثبت می‌شن - یعنی یه منبعِ
واحد برایِ زمان‌بندی به‌جایِ ۴ Threadِ همیشه‌بیدار + یک Scheduler.
هر تابع الان فقط یک اجرا انجام می‌ده (بدونِ حلقه/sleep)؛ خودِ
Schedulerِ APScheduler تکرارش می‌کنه.
"""
from base.paths import ROOT
import io
import os
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from base import database as db
from features import notifications
from ops import backup_manager
from base.core import (
    bot, log, report_error, clear_state,
    _states, _states_lock, _last_activity, _last_activity_lock,
    S_WAIT_GROUP_HASHTAG, S_WAIT_GROUP_CONTENT, S_WAIT_GROUP_NAME,
    S_WAIT_GROUP_REEL_CONTENT, S_WAIT_GROUP_STORY_CONTENT,
)
from bot.keyboards import user_main_menu

def _flood_unblock_notifier():
    """هر بار صدا زده بشه، چک می‌کند چه کسانی مسدودی موقت ۳۰ دقیقه‌ای‌شان
    تمام شده و هنوز پیام «بخشیدمت» را نگرفته‌اند. (هر ۶۰ ثانیه - نگاه کن main.py)"""
    try:
        for uid in db.get_expired_temp_blocks():
            try:
                db.flood_clear_temp_block(uid)
                bot.send_message(
                    uid,
                    'اینبارو بخشیدمت ولی بار دیگه میرم به بابام میگم 😤'
                )
            except Exception as e:
                log.warning('Flood unblock notify %s failed: %s', uid, e)
    except Exception as e:
        report_error('Flood unblock notifier', e)

def _cooldown_notifier():
    """هر ۳۰ ثانیه - نگاه کن main.py."""
    try:
        for uid in db.get_users_to_notify():
            try:
                zone_id = db.get_user_zone_id(uid)
                allowance = db.get_text_allowance(zone_id)
                notify_msg = db.get_zone_setting(zone_id, 'unlock_msg', None) or (
                    f'🎉 محدودیت شما رفع شد!\n'
                    f'می‌توانید مجدداً تا سقف {allowance} متن دریافت کنید.'
                )
                bot.send_message(uid, notify_msg, reply_markup=user_main_menu())
                pu = db.get_panel_user_by_telegram_id(uid)
                if pu:
                    notifications.notify('rate_limit_lifted', [('friend', pu['id'])])
            except Exception as e:
                log.warning('Notify %s failed: %s', uid, e)
            finally:
                db.mark_user_notified(uid)
    except Exception as e:
        log.error('Cooldown notifier error: %s', e)

def _inactive_user_notifier():
    """هر ۵ دقیقه (۳۰۰ ثانیه) - نگاه کن main.py."""
    try:
        now = datetime.utcnow()
        with _last_activity_lock:
            inactive = {uid: last for uid, last in list(_last_activity.items())
                        if (now - last).total_seconds() >= 3600}
        for uid in inactive:
            try:
                kb = ReplyKeyboardMarkup(resize_keyboard=True)
                kb.add(KeyboardButton('/start'))
                bot.send_message(uid, 'برای اجرای ربات لطفاً روی /start بزنید.', reply_markup=kb)
            except Exception:
                pass
            finally:
                with _last_activity_lock:
                    _last_activity.pop(uid, None)
    except Exception as e:
        log.error('Inactive notifier error: %s', e)

def _record_backup_status(ok, size=0, nfiles=0, sent=False, error=''):
    """نتیجهٔ آخرین بک‌آپ در `settings` ذخیره می‌شود (برایِ داشبوردِ سلامتِ A7)."""
    try:
        now = datetime.now(ZoneInfo('Asia/Tehran')).isoformat(timespec='seconds')
        db.set_setting('backup_last_ts', now)
        db.set_setting('backup_last_ok', '1' if ok else '0')
        db.set_setting('backup_last_size', str(int(size or 0)))
        db.set_setting('backup_last_files', str(int(nfiles or 0)))
        db.set_setting('backup_last_sent', '1' if sent else '0')
        db.set_setting('backup_last_error', (error or '')[:300])
        if ok:
            db.set_setting('backup_last_ok_ts', now)
    except Exception as e:
        log.warning('Backup status save failed: %s', e)

def _auto_backup():
    """بک‌آپِ روزانه (۱۴:۰۰ تهران): عکسِ سازگار از DB (sqlite backup API) + کد +
    web_static + آواتارها؛ تأییدِ سلامت؛ چرخشِ ۷ نسخه‌یِ محلی؛ ارسال به مالک
    (اگر از سقفِ تلگرام بزرگ‌تر بود چندتکه). در هر شکستی به مالک هشدار می‌رود
    و وضعیت در settings ثبت می‌شود. جزئیات: backup_manager.py"""
    try:
        res = backup_manager.make_backup()
        if not res['ok']:
            _record_backup_status(False, error=res.get('error') or '')
            report_error('Auto-backup (ساخت)', Exception(res.get('error') or 'نامشخص'))
            return
        files = res['files']
        owner_id = db.get_owner_id()
        sent = False
        send_err = ''
        if owner_id:
            now = datetime.now(ZoneInfo('Asia/Tehran'))
            total = len(files)
            try:
                for i, fp in enumerate(files, 1):
                    part_txt = f' — تکهٔ {i} از {total}' if total > 1 else ''
                    caption = (
                        f'📦 پشتیبان‌گیری خودکار (روزانه، ساعت ۱۴:۰۰ تهران){part_txt}\n'
                        f'🗓 {now.strftime("%Y-%m-%d")}  ⏰ {now.strftime("%H:%M")} (تهران)\n'
                        f'✅ سلامتِ دیتابیس تأیید شد · حجم: {backup_manager.human_size(res["size"])}'
                    )
                    if total > 1 and i == 1:
                        caption += ('\n⚠️ بک‌آپ چندتکه است؛ برایِ بازیابی همهٔ تکه‌ها را '
                                    'کنارِ هم بگذار و restore_backup.py را روی تکهٔ .001 بزن.')
                    with open(fp, 'rb') as fh:
                        bot.send_document(owner_id, fh, caption=caption,
                                          visible_file_name=os.path.basename(fp),
                                          timeout=300)
                sent = True
            except Exception as e:
                send_err = f'ارسال به تلگرام ناموفق: {e}'
                log.error('Auto-backup send failed: %s', e)
        # بک‌آپِ محلی ساخته شده؛ حتی اگر ارسال نشد، نسخهٔ روی سرور هست
        _record_backup_status(True, size=res['size'], nfiles=len(files),
                              sent=sent, error=send_err)
        if send_err:
            report_error('Auto-backup (ارسال)',
                         Exception(send_err + ' — نسخهٔ محلی روی سرور ساخته شد (پوشهٔ backups).'))
    except Exception as e:
        _record_backup_status(False, error=str(e))
        report_error('Auto-backup', e)

def _group_timeout_checker():
    """
    بعد از ۱۰ دقیقه بی‌فعالیت، state ادمین در گروه به‌طور کاملاً بی‌صدا پاک
    می‌شود — بدون هیچ پیام یا واکنشی (طبق خواسته: «هیچ عکس‌العملی انجام نده»).
    (هر ۶۰ ثانیه - نگاه کن main.py)
    """
    GROUP_CONTENT_STATES = (
        S_WAIT_GROUP_CONTENT, S_WAIT_GROUP_HASHTAG, S_WAIT_GROUP_NAME,
        S_WAIT_GROUP_REEL_CONTENT, S_WAIT_GROUP_STORY_CONTENT,
    )
    try:
        now = datetime.utcnow()
        with _states_lock:
            to_clear = [
                key for key, val in list(_states.items())
                if val.get('state') in GROUP_CONTENT_STATES
                and (now - val.get('set_at', now)).total_seconds() > 600
            ]
        for uid, cid in to_clear:
            clear_state(uid, cid)
    except Exception as e:
        log.error('Group timeout checker error: %s', e)
