# -*- coding: utf-8 -*-
"""بک‌آپِ امن و قابلِ‌اعتماد (کارِ A1).

چرا ماژولِ جدید؟ نسخهٔ قبلیِ `_auto_backup` فایلِ `bot_data.db` را مستقیم کپی
می‌کرد. دیتابیس در حالتِ WAL است و ربات و وب هر دو همزمان روی آن می‌نویسند؛
کپیِ مستقیمِ فایل ممکن است ناقص یا ناسازگار (بدونِ `-wal`) باشد. همچنین
سقفِ ۵۰مگابایتیِ آپلودِ تلگرام با رشدِ دیتابیس بی‌صدا شکست می‌خورد.

این ماژول:
  • از `sqlite3.Connection.backup()` استفاده می‌کند (عکسِ سازگار، حتی وسطِ نوشتن)؛
  • روی عکس `PRAGMA integrity_check` می‌زند؛ اگر سالم نبود **چرخش انجام نمی‌شود**
    تا نسخه‌هایِ سالمِ قبلی پاک نشوند؛
  • zip را با `BACKUP_INFO.json` (مجموعِ کنترلیِ sha256) می‌سازد؛
  • اگر از سقفِ تلگرام بزرگ‌تر شد به چند تکه (`.zip.001`, `.002`, …) می‌شکند؛
  • چند نسخهٔ آخر را روی خودِ سرور نگه می‌دارد (پیش‌فرض ۷ تا)؛
  • بک‌آپِ رسانه‌هایِ چت را جدا و فقط محلی نگه می‌دارد (حجمِ زیاد، برایِ تلگرام نیست).

هیچ وابستگی‌ای به ربات/تلگرام ندارد (تا بشود تنهایی تست کرد)؛ ارسال و ثبتِ وضعیت
در `background_jobs.py` انجام می‌شود. رمزها/توکن‌ها (`.bot_token` و …) عمداً
داخلِ بک‌آپ **نیستند** چون فایل به تلگرام می‌رود.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from base.paths import ROOT
import glob
import hashlib
import json
import os
import shutil
import sqlite3
import time
import zipfile
from datetime import datetime

BASE_DIR = ROOT
DB_NAME = 'bot_data.db'
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

KEEP_LOCAL = 7                    # تعدادِ نسخه‌هایِ نگه‌داشته‌شده روی سرور
KEEP_MEDIA = 2                    # تعدادِ بک‌آپِ رسانه
TG_PART_LIMIT = 45 * 1024 * 1024  # سقفِ هر تکه؛ زیرِ ۵۰مگابایتِ تلگرام با حاشیه
MIN_FREE_FACTOR = 2.0             # برایِ ساختنِ بک‌آپ دیسک باید این‌قدر برابرِ حجمِ DB خالی باشد

# پوشه‌هایی که داخلِ بک‌آپِ اصلی می‌روند (کوچک و مهم)
CORE_DIRS = ('web_static', 'chat_avatars', 'news_media', 'base', 'bot', 'features', 'ops', 'deploy', 'docs')
# پسوندِ فایل‌هایِ کنارِ پروژه که داخلِ بک‌آپِ اصلی می‌روند
CORE_EXTS = ('.py', '.sh', '.service', '.conf', '.txt')
# بک‌آپِ رسانه (فقط محلی)
MEDIA_DIRS = ('chat_media',)


class BackupError(Exception):
    pass


def _ts(now=None):
    return (now or datetime.now()).strftime('%Y%m%d_%H%M%S')


def _sha256(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def snapshot_db(src_path, dst_path):
    """عکسِ سازگار از دیتابیسِ زنده با APIِ رسمیِ SQLite (نه کپیِ فایل).
    برمی‌گرداند: dict(ok, integrity, tables, size)."""
    if not os.path.isfile(src_path):
        raise BackupError('فایلِ دیتابیس پیدا نشد: %s' % src_path)
    if os.path.exists(dst_path):
        os.remove(dst_path)
    src = sqlite3.connect(src_path, timeout=30)
    dst = sqlite3.connect(dst_path)
    try:
        # pages=-1: یک‌جا و اتمیک. در WAL خواننده جلویِ نویسنده را نمی‌گیرد.
        src.backup(dst)
        # عکس را به حالتِ تک‌فایل ببریم تا -wal/-shm لازم نباشد
        dst.execute('PRAGMA journal_mode=DELETE')
        rows = dst.execute('PRAGMA integrity_check').fetchall()
        integrity = rows[0][0] if rows else 'no-result'
        tables = dst.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    finally:
        dst.close()
        src.close()
    return {
        'ok': integrity == 'ok' and tables > 0,
        'integrity': integrity,
        'tables': tables,
        'size': os.path.getsize(dst_path),
    }


def _iter_core_files(base_dir):
    """(مسیرِ واقعی، نامِ داخلِ zip) برایِ فایل‌هایِ بک‌آپِ اصلی (بدونِ DB)."""
    for fname in sorted(os.listdir(base_dir)):
        fp = os.path.join(base_dir, fname)
        if (os.path.isfile(fp) and fname.endswith(CORE_EXTS)
                and not fname.startswith('.')):
            yield fp, fname
    for d in CORE_DIRS:
        root = os.path.join(base_dir, d)
        if not os.path.isdir(root):
            continue
        for dp, dn, fns in os.walk(root):
            dn[:] = [x for x in dn if x not in ('__pycache__',)]
            for fn in fns:
                fp = os.path.join(dp, fn)
                yield fp, os.path.relpath(fp, base_dir).replace(os.sep, '/')


def _split_file(path, part_size):
    """فایل را به تکه‌هایِ `path.001`, `.002`, … می‌شکند و فایلِ اصلی را پاک می‌کند."""
    parts = []
    with open(path, 'rb') as f:
        i = 1
        while True:
            chunk = f.read(part_size)
            if not chunk:
                break
            pp = '%s.%03d' % (path, i)
            with open(pp, 'wb') as o:
                o.write(chunk)
            parts.append(pp)
            i += 1
    os.remove(path)
    return parts


def _free_bytes(path):
    return shutil.disk_usage(path).free


def make_backup(base_dir=BASE_DIR, backup_dir=None, part_limit=None,
                keep=None, now=None):
    """بک‌آپِ اصلی (DB + کد + web_static + آواتارها) را می‌سازد.

    برمی‌گرداند: dict با کلیدهایِ ok, files (فهرستِ مسیرها)، size، db، error.
    خطا را پرتاب نمی‌کند؛ نتیجه را در dict گزارش می‌دهد تا صدازننده هشدار بدهد.
    """
    backup_dir = backup_dir or (BACKUP_DIR if base_dir == BASE_DIR
                                else os.path.join(base_dir, 'backups'))
    part_limit = part_limit or TG_PART_LIMIT
    keep = keep or KEEP_LOCAL
    res = {'ok': False, 'files': [], 'size': 0, 'db': None, 'error': None,
           'ts': (now or datetime.now()).isoformat(timespec='seconds')}
    tmp_db = None
    try:
        os.makedirs(backup_dir, exist_ok=True)
        db_path = os.path.join(base_dir, DB_NAME)
        if not os.path.isfile(db_path):
            raise BackupError('فایلِ دیتابیس پیدا نشد')
        # فضایِ خالی: عکسِ DB + zip ≈ دو برابرِ حجمِ DB (با حاشیه)
        need = int(os.path.getsize(db_path) * MIN_FREE_FACTOR) + 20 * 1024 * 1024
        if _free_bytes(backup_dir) < need:
            raise BackupError('فضایِ دیسک برایِ بک‌آپ کافی نیست')

        stamp = _ts(now)
        tmp_db = os.path.join(backup_dir, '.snapshot_%s.db' % stamp)
        snap = snapshot_db(db_path, tmp_db)
        res['db'] = snap
        if not snap['ok']:
            # نسخهٔ خراب را نگه نمی‌داریم و چرخش هم انجام نمی‌شود
            raise BackupError('بررسیِ سلامتِ دیتابیس ناموفق: %s' % snap['integrity'])

        db_hash = _sha256(tmp_db)
        out = os.path.join(backup_dir, 'backup_%s.zip' % stamp)
        info = {
            'format': 1,
            'created': res['ts'],
            'db_file': DB_NAME,
            'db_sha256': db_hash,
            'db_size': snap['size'],
            'integrity': snap['integrity'],
            'tables': snap['tables'],
            'note': 'رمزها/توکن‌ها عمداً داخلِ این بک‌آپ نیستند',
        }
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(tmp_db, DB_NAME)
            for fp, arc in _iter_core_files(base_dir):
                try:
                    zf.write(fp, arc)
                except OSError:
                    continue  # فایلی که همان لحظه پاک شد
            zf.writestr('BACKUP_INFO.json',
                        json.dumps(info, ensure_ascii=False, indent=2))
        # تأییدِ خودِ zip
        with zipfile.ZipFile(out) as zf:
            bad = zf.testzip()
            if bad:
                raise BackupError('فایلِ zip خراب است: %s' % bad)

        files = [out]
        if os.path.getsize(out) > part_limit:
            files = _split_file(out, part_limit)
        res['files'] = files
        res['size'] = sum(os.path.getsize(p) for p in files)
        res['ok'] = True
        rotate(backup_dir, keep=keep, prefix='backup_')
    except Exception as e:  # noqa: BLE001
        res['error'] = '%s: %s' % (type(e).__name__, e)
    finally:
        if tmp_db and os.path.exists(tmp_db):
            try:
                os.remove(tmp_db)
            except OSError:
                pass
    return res


def make_media_backup(base_dir=BASE_DIR, backup_dir=None, keep=None, now=None):
    """بک‌آپِ رسانه‌هایِ چت (فقط محلی، بدونِ فشرده‌سازی چون عکس/ویدیو از قبل فشرده‌اند).
    اگر فضایِ خالی کم بود انجام نمی‌شود (ایمنی؛ سرور دیسکِ محدود دارد)."""
    backup_dir = backup_dir or (BACKUP_DIR if base_dir == BASE_DIR
                                else os.path.join(base_dir, 'backups'))
    keep = keep or KEEP_MEDIA
    res = {'ok': False, 'files': [], 'size': 0, 'error': None, 'skipped': False,
           'ts': (now or datetime.now()).isoformat(timespec='seconds')}
    try:
        os.makedirs(backup_dir, exist_ok=True)
        entries, total = [], 0
        for d in MEDIA_DIRS:
            root = os.path.join(base_dir, d)
            if not os.path.isdir(root):
                continue
            for dp, _dn, fns in os.walk(root):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        continue
                    entries.append((fp, os.path.relpath(fp, base_dir).replace(os.sep, '/')))
        if not entries:
            res['skipped'] = True
            res['ok'] = True
            return res
        # حداقل ۲ برابرِ حجم + ۵۰۰مگابایت باید خالی باشد، وگرنه دیسک را پر نمی‌کنیم
        if _free_bytes(backup_dir) < total * 2 + 500 * 1024 * 1024:
            res['skipped'] = True
            res['error'] = 'فضایِ دیسک برایِ بک‌آپِ رسانه کافی نیست (رد شد)'
            return res
        out = os.path.join(backup_dir, 'media_%s.zip' % _ts(now))
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as zf:
            for fp, arc in entries:
                try:
                    zf.write(fp, arc)
                except OSError:
                    continue
        res['files'] = [out]
        res['size'] = os.path.getsize(out)
        res['ok'] = True
        rotate(backup_dir, keep=keep, prefix='media_')
    except Exception as e:  # noqa: BLE001
        res['error'] = '%s: %s' % (type(e).__name__, e)
    return res


def _group_key(name, prefix):
    """نامِ پایه‌یِ یک بک‌آپ (تکه‌ها `.zip.001` یک گروه‌اند)."""
    base = name
    if '.zip.' in base:
        base = base.split('.zip.')[0] + '.zip'
    return base


def rotate(backup_dir, keep, prefix):
    """فقط `keep` گروهِ آخر را نگه می‌دارد (گروه = یک zip یا همهٔ تکه‌هایش)."""
    groups = {}
    for p in glob.glob(os.path.join(backup_dir, prefix + '*')):
        name = os.path.basename(p)
        if not (name.endswith('.zip') or '.zip.' in name):
            continue
        groups.setdefault(_group_key(name, prefix), []).append(p)
    ordered = sorted(groups)  # نامِ بر پایهٔ زمان است؛ ترتیبِ الفبایی = زمانی
    removed = []
    for key in ordered[:-keep] if keep > 0 else ordered:
        for p in groups[key]:
            try:
                os.remove(p)
                removed.append(p)
            except OSError:
                pass
    return removed


def list_backups(backup_dir=BACKUP_DIR, prefix='backup_'):
    """فهرستِ بک‌آپ‌هایِ محلی: [(نامِ پایه, اندازهٔ کل, تعدادِ تکه)] از قدیم به جدید."""
    groups = {}
    for p in glob.glob(os.path.join(backup_dir, prefix + '*')):
        name = os.path.basename(p)
        if name.endswith('.zip') or '.zip.' in name:
            groups.setdefault(_group_key(name, prefix), []).append(p)
    out = []
    for k in sorted(groups):
        out.append((k, sum(os.path.getsize(x) for x in groups[k]), len(groups[k])))
    return out


def human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return ('%d %s' % (n, unit)) if unit == 'B' else ('%.1f %s' % (n, unit))
        n /= 1024.0
