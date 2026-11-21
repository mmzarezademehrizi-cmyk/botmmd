# -*- coding: utf-8 -*-
"""نقطه‌ی ورود ربات: راه‌اندازی، ثبت دستورات، استارت Threadها و scheduler، polling."""
import os
import time

from base.paths import ROOT
from apscheduler.schedulers.background import BackgroundScheduler

from base import database as db
from base import config
from base.core import bot, log, report_error
from bot.admin_ops import _set_admin_commands, _set_user_commands
from bot.background_jobs import (
    _cooldown_notifier, _inactive_user_notifier, _auto_backup, _group_timeout_checker,
    _flood_unblock_notifier,
)

# ثبت هندلرها: صرفاً با ایمپورت این ماژول‌ها، دکوریتورهای @bot.message_handler و
# @bot.callback_query_handler داخلشون روی همین یک نمونه bot (از core) ثبت می‌شوند.
from bot import handlers_private
from bot import handlers_group
from bot import handlers_callback

def _load_owner_id():
    """آیدیِ عددیِ تلگرامِ مالک: از متغیرِ محیطیِ OWNER_ID یا فایلِ .owner_id (کنارِ main.py)."""
    raw = (os.environ.get('OWNER_ID') or '').strip()
    if not raw:
        try:
            with open(os.path.join(ROOT, '.owner_id'), encoding='utf-8') as f:
                raw = f.read().strip()
        except OSError:
            raw = ''
    return int(raw) if raw.isdigit() else None


def main():
    # امنیتی: اگه BOT_TOKEN اصلاً تنظیم نشده (نه env var نه .bot_token)،
    # config.py یه مقدارِ ساختگی برگردونده تا صرفاً import کردنِ ماژول‌ها
    # (مثلاً تویِ تست‌ها) کرش نکنه - ولی خودِ اجرایِ واقعیِ بات نباید با
    # این مقدارِ ساختگی جلو بره (وگرنه فقط یه حلقه‌ی بی‌نهایتِ خطایِ ۴۰۱ از
    # تلگرام می‌شه). اینجا، جایی که واقعاً می‌خوایم پولینگ رو شروع کنیم،
    # صریحاً چکش می‌کنیم.
    if config.BOT_TOKEN == config._PLACEHOLDER_TOKEN:
        log.error(
            'BOT_TOKEN تنظیم نشده - بات استارت نمی‌شه. متغیرِ محیطیِ BOT_TOKEN رو '
            'ست کن یا توکن رو توی فایلِ .bot_token کنارِ همین پروژه بذار (توکنِ '
            'تازه از @BotFather بگیر، نه توکنِ قدیمیِ سوخته‌شده).'
        )
        return
    db.init_db()
    oid = _load_owner_id()
    if oid and db.get_owner_id() != oid:
        db.set_setting('owner_id', str(oid))
        log.info('مالکِ ربات تنظیم شد: %s', oid)
    try:
        bot.remove_webhook()
    except Exception as e:
        log.warning('remove_webhook failed (probably fine): %s', e)
    _set_user_commands()
    owner_id = db.get_owner_id()
    if owner_id:
        _set_admin_commands(owner_id)
    else:
        log.warning(
            'مالک هنوز تعیین نشده. آیدیِ عددیِ تلگرامِ خودت رو (از @userinfobot) توی فایلِ '
            '.owner_id کنارِ main.py بنویس (یا متغیرِ محیطیِ OWNER_ID) و ربات رو ریستارت کن.'
        )
    for a in db.get_all_bot_admins():
        _set_admin_commands(a['user_id'])

    # فازِ ادامه (بهبودِ عملکرد): این ۴ تا قبلاً هرکدوم Threadِ جداگونه‌ی
    # همیشه‌بیدار با time.sleep بودن؛ الان همه با همون یک BackgroundScheduler
    # زمان‌بندی می‌شن (بازه‌ها دقیقاً همونی‌ه که قبلاً تو خودِ حلقه‌ها بود).
    scheduler = BackgroundScheduler(timezone='Asia/Tehran')
    scheduler.add_job(_auto_backup,             'cron',     hour=14, minute=0,  id='backup', max_instances=1, misfire_grace_time=3600)
    scheduler.add_job(_cooldown_notifier,       'interval', seconds=30,  id='cooldown',       max_instances=1)
    scheduler.add_job(_inactive_user_notifier,  'interval', seconds=300, id='inactive',       max_instances=1)
    scheduler.add_job(_group_timeout_checker,   'interval', seconds=60,  id='group-timeout',  max_instances=1)
    scheduler.add_job(_flood_unblock_notifier,  'interval', seconds=60,  id='flood-unblock',  max_instances=1)
    scheduler.start()

    log.info('Bot starting...')
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            report_error('Polling crashed', e)
            time.sleep(5)

if __name__ == '__main__':
    main()
