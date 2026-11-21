from base.paths import ROOT
import sqlite3
import os
import hashlib
import secrets
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

DB_PATH = os.path.join(ROOT, 'bot_data.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            last_name     TEXT,
            registered_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_cooldown (
            user_id      INTEGER PRIMARY KEY,
            texts_sent   INTEGER DEFAULT 0,
            locked_until TEXT DEFAULT NULL,
            notified     INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS hashtags (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT UNIQUE NOT NULL,
            is_active  INTEGER DEFAULT 0,
            append_tag INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS texts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT NOT NULL,
            hashtag_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (hashtag_id) REFERENCES hashtags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS photos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id    TEXT NOT NULL,
            hashtag_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (hashtag_id) REFERENCES hashtags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bot_groups (
            group_id   INTEGER PRIMARY KEY,
            group_name TEXT,
            group_link TEXT DEFAULT 'N/A',
            joined_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS group_admins (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            added_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bot_admins (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            added_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_received_photos (
            user_id  INTEGER,
            photo_id INTEGER,
            PRIMARY KEY (user_id, photo_id)
        );

        CREATE TABLE IF NOT EXISTS vip_users (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            added_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS instagram_vip_users (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            added_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reels (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            hashtag_id INTEGER,
            file_id    TEXT NOT NULL,
            caption    TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS stories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            hashtag_id INTEGER,
            file_id    TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_received_reels (
            user_id INTEGER,
            reel_id INTEGER,
            PRIMARY KEY (user_id, reel_id)
        );

        CREATE TABLE IF NOT EXISTS user_received_stories (
            user_id  INTEGER,
            story_id INTEGER,
            PRIMARY KEY (user_id, story_id)
        );

        -- کول‌داون مشترک برای انواع محتوای اینستاگرام (content_type: 'reel' | 'story')
        CREATE TABLE IF NOT EXISTS user_content_cooldown (
            user_id      INTEGER,
            content_type TEXT,
            sent_count   INTEGER DEFAULT 0,
            locked_until TEXT DEFAULT NULL,
            notified     INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, content_type)
        );

        -- آنتی‌فلود: تخلف اول = مسدودی موقت ۳۰ دقیقه‌ای، تخلف دوم به بعد = مسدودی دائم
        CREATE TABLE IF NOT EXISTS user_flood (
            user_id              INTEGER PRIMARY KEY,
            offense_count        INTEGER DEFAULT 0,
            blocked_until        TEXT DEFAULT NULL,
            permanently_blocked  INTEGER DEFAULT 0,
            notice_chat_id       INTEGER,
            notice_msg_id        INTEGER
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- ناحیه‌ها: با پنل ادمین اضافه می‌شوند، هر کاربر پنل عضو یکی از این‌هاست
        CREATE TABLE IF NOT EXISTS zones (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- شش «اسلاتِ» آیکون اپ (بخش انتخاب آیکون لانچر). چون آیکون
        -- واقعیِ لانچر باید موقع build داخل خود اپ باشه (سیستم‌عامل
        -- اجازه نمی‌ده از یه عکس دلخواه در لحظه بسازیمش)، این جدول
        -- فقط «متادیتا»ی همون ۶ اسلاتِ از پیش تعریف‌شده رو نگه می‌داره:
        -- اسمش چیه، پیش‌نمایشش (که مالک آپلود می‌کنه) چیه، فعاله یا نه،
        -- و کدوم ناحیه‌ها بهش دسترسی دارن.
        CREATE TABLE IF NOT EXISTS app_icon_slots (
            id            INTEGER PRIMARY KEY,   -- ۱ تا ۶، معادل همون
                                                   -- activity-alias های اندروید
            label         TEXT NOT NULL,
            preview_path  TEXT,
            enabled       INTEGER NOT NULL DEFAULT 1,
            all_zones     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS app_icon_slot_zones (
            icon_slot_id  INTEGER NOT NULL,
            zone_id       INTEGER NOT NULL,
            PRIMARY KEY (icon_slot_id, zone_id)
        );

        -- حساب‌های پنل ورود (یوزرنیم/پسورد) — مجزا از رجیستر خودکار تلگرامی
        -- کاربران (جدول users). رمز هرگز به‌صورت متن ساده ذخیره نمی‌شود، فقط
        -- هش (password_hash) نگه داشته می‌شود.
        CREATE TABLE IF NOT EXISTS panel_users (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            username          TEXT UNIQUE NOT NULL,
            password_hash     TEXT NOT NULL,
            zone_id           INTEGER NOT NULL,
            telegram_user_id  INTEGER,
            created_at        TEXT DEFAULT (datetime('now')),
            last_login_at     TEXT DEFAULT NULL,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_texts_hashtag   ON texts(hashtag_id);
        CREATE INDEX IF NOT EXISTS idx_photos_hashtag  ON photos(hashtag_id);
        CREATE INDEX IF NOT EXISTS idx_panel_users_zone ON panel_users(zone_id);

        -- تنظیمات مخصوص هر ناحیه (محدودیت‌ها، پیام‌ها). اگر برای یک کلید در
        -- یک ناحیه چیزی ثبت نشده باشد، در get_zone_setting به‌صورت خودکار
        -- روی مقدار سراسری settings برمی‌گردیم.
        CREATE TABLE IF NOT EXISTS zone_settings (
            zone_id INTEGER NOT NULL,
            key     TEXT NOT NULL,
            value   TEXT,
            PRIMARY KEY (zone_id, key),
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );

        -- سرپرست‌ها (افراد): یک panel_user که مالک ربات به او اجازه داده رمز
        -- کاربرانِ یک یا چند ناحیه را ببیند (علاوه بر دسترسی عادی محتوایش).
        CREATE TABLE IF NOT EXISTS supervisor_zones (
            panel_user_id INTEGER NOT NULL,
            zone_id       INTEGER NOT NULL,
            PRIMARY KEY (panel_user_id, zone_id),
            FOREIGN KEY (panel_user_id) REFERENCES panel_users(id) ON DELETE CASCADE,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );

        -- فرمانده‌ها: یک panel_user که مالک بهش اختیارِ مدیریتیِ محدود (نه
        -- کاملِ مالک) روی یک یا چند ناحیه‌ی مشخص داده. سه جدول:
        --   commanders          - همین که یه ردیف اینجا داره یعنی فرمانده‌ست.
        --   commander_zones     - این فرمانده روی کدوم ناحیه(ها) اختیار داره.
        --   commander_permissions - این فرمانده اجازه‌ی کدوم اکشن‌ها رو داره
        --      (کلیدها تو COMMANDER_PERMISSIONS پایینِ همین فایل مستندن).
        -- فرمانده با همون یوزرنیم/پسوردِ panel_users خودش لاگین می‌کنه (لاگین
        -- جدا نداره)؛ نقشش تو session با is_commander مشخص می‌شه، نه یه role
        -- جدا - چون فرمانده هنوز هم می‌تونه به‌عنوانِ friendِ عادی از محتوایِ
        -- ناحیه‌ی خودش استفاده کنه؛ فرماندگی یه لایه‌ی اضافه‌ست، نه جایگزین.
        CREATE TABLE IF NOT EXISTS commanders (
            panel_user_id INTEGER PRIMARY KEY,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (panel_user_id) REFERENCES panel_users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS commander_zones (
            panel_user_id INTEGER NOT NULL,
            zone_id       INTEGER NOT NULL,
            PRIMARY KEY (panel_user_id, zone_id),
            FOREIGN KEY (panel_user_id) REFERENCES panel_users(id) ON DELETE CASCADE,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS commander_permissions (
            panel_user_id INTEGER NOT NULL,
            perm_key      TEXT NOT NULL,
            PRIMARY KEY (panel_user_id, perm_key),
            FOREIGN KEY (panel_user_id) REFERENCES panel_users(id) ON DELETE CASCADE
        );

        -- چند-مالکی از طریقِ تلگرام: علاوه بر مالکِ اصلی/اولیه (که آیدیش تو
        -- settings زیرِ کلیدِ owner_id ذخیره‌ست و دست‌نخورده می‌مونه)، مالک
        -- می‌تونه چند تلگرام‌آیدیِ دیگه رو هم به‌عنوانِ «مالکِ اضافه» معرفی
        -- کنه؛ هرکسی با یکی از این آیدی‌ها وارد بات بشه، is_owner()==True
        -- می‌شه (دسترسیِ کاملِ مالک تو بات، نه پنل/اپ - اونجا هنوز لازمه
        -- یوزرنیم/پسوردِ owner رو داشته باشه).
        CREATE TABLE IF NOT EXISTS owner_accounts (
            telegram_user_id INTEGER PRIMARY KEY,
            name             TEXT NOT NULL,
            added_at         TEXT DEFAULT (datetime('now'))
        );

        -- هشتگ می‌تونه مال چند ناحیه‌ی مشخص باشه (نه فقط یکی یا همه). اگر
        -- هیچ ردیفی برای یک هشتگ اینجا نباشه، یعنی طبق ستون قدیمی زون_ای‌دی
        -- عمل می‌شه (سازگاری با هشتگ‌های قدیمی)، که NULL آن یعنی «برای همه».
        CREATE TABLE IF NOT EXISTS hashtag_zones (
            hashtag_id INTEGER NOT NULL,
            zone_id    INTEGER NOT NULL,
            PRIMARY KEY (hashtag_id, zone_id),
            FOREIGN KEY (hashtag_id) REFERENCES hashtags(id) ON DELETE CASCADE,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );
        -- محدودیت تلاش ورود اشتباه (چه از ربات چه از سایت) — جلوگیری از
        -- حدس‌زدن پسورد با تلاش‌های پیاپی.
        CREATE TABLE IF NOT EXISTS login_attempts (
            identifier   TEXT PRIMARY KEY,
            attempts     INTEGER DEFAULT 0,
            locked_until TEXT DEFAULT NULL
        );

        -- محدودیت جدا و بسیار سبک‌تر برای چک کد قفل ماشین‌حساب: چون این
        -- endpoint با هر بار زدن «مساوی» (حتی محاسبات کاملاً عادی و
        -- بی‌ربط) صدا زده می‌شه، نباید از همون قانون سخت‌گیرانه‌ی ورود
        -- (۳ تلاش/۱ ساعت قفل) استفاده کنه - وگرنه استفاده‌ی عادی از
        -- ماشین‌حساب باعث قفل‌شدن می‌شه.
        CREATE TABLE IF NOT EXISTS app_lock_attempts (
            identifier   TEXT PRIMARY KEY,
            attempts     INTEGER DEFAULT 0,
            window_start TEXT DEFAULT NULL,
            locked_until TEXT DEFAULT NULL
        );

        -- نوتیفیکیشن پوش: انواعِ سیستمی (وصل به رویدادهای واقعی کد) که
        -- مالک می‌تونه هرکدوم رو خاموش/روشن یا متنش رو ویرایش کنه.
        CREATE TABLE IF NOT EXISTS notification_types (
            key         TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            template    TEXT NOT NULL,
            enabled     INTEGER DEFAULT 1
        );

        -- ترجیح شخصیِ هر کاربر برای هر نوع نوتیف - جدا از سوییچ سراسری
        -- بالا (که مالک برای همه روشن/خاموش می‌کنه). اگه ردیفی نباشه
        -- یعنی پیش‌فرض روشنه. مثال: کاربری که نمی‌خواد با تغییر
        -- دسترسی‌هاش تو گروه پوش بگیره.
        CREATE TABLE IF NOT EXISTS user_notification_prefs (
            panel_user_id INTEGER NOT NULL,
            notif_key     TEXT NOT NULL,
            enabled       INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (panel_user_id, notif_key)
        );

        -- توکن FCM هر کاربر (هر گوشی/مرورگری که push رو فعال کرده).
        CREATE TABLE IF NOT EXISTS push_tokens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            role          TEXT NOT NULL,           -- 'owner' | 'friend'
            panel_user_id INTEGER,                  -- فقط برای role='friend'
            token         TEXT NOT NULL UNIQUE,
            platform      TEXT,                      -- 'android' | 'ios' | 'web'
            created_at    TEXT DEFAULT (datetime('now'))
        );

        -- برای جلوگیری از اسپم: وقتی ادمین چندین آیتم پشت‌سرهم به یه
        -- هشتگ اضافه می‌کنه، فقط یک نوتیف در هر بازه‌ی زمانی می‌ره، نه
        -- یکی به‌ازای هر آیتم.
        CREATE TABLE IF NOT EXISTS content_notify_debounce (
            hashtag_id  INTEGER NOT NULL,
            kind        TEXT NOT NULL,               -- text|photo|reel|story
            last_sent   TEXT NOT NULL,
            PRIMARY KEY (hashtag_id, kind)
        );

        -- توکن‌های API — برای اپلیکیشن موبایل (یا هر کلاینت دیگه‌ای غیر از
        -- مرورگر/تلگرام) که نمی‌تونه از کوکی/سشن استفاده کنه.
        CREATE TABLE IF NOT EXISTS api_tokens (
            token         TEXT PRIMARY KEY,
            role          TEXT,
            panel_user_id INTEGER,
            created_at    TEXT DEFAULT (datetime('now')),
            last_used_at  TEXT DEFAULT NULL,
            FOREIGN KEY (panel_user_id) REFERENCES panel_users(id) ON DELETE CASCADE
        );

        -- تاریخچه‌ی محتوای دریافتی هر کاربر (متن/عکس/ریلز/استوری). فقط
        -- برای درخواست‌هایی که از الان به بعد میان ثبت می‌شه (متن‌های قبلی
        -- که قبلاً pop شدن قابل بازیابی نیستن چون خودِ ردیفشون حذف شده).
        CREATE TABLE IF NOT EXISTS content_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            content_uid   INTEGER NOT NULL,
            kind          TEXT NOT NULL,   -- 'text' | 'photo' | 'reel' | 'story'
            hashtag_id    INTEGER,
            media_type    TEXT,            -- 'photo' | 'video' (فقط برای عکس/ریلز/استوری)
            ref_id        INTEGER,         -- id ردیف اصلی (photos.id/reels.id/stories.id)
            text_content  TEXT,            -- فقط برای kind='text'
            caption       TEXT,            -- فقط برای ریلز
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_content_history_uid
            ON content_history(content_uid, created_at DESC);
        """)

        # مقادیر پیش‌فرض settings
        defaults = [
            ('operation_active',   'false'),
            ('admin_contact',      'برای ارتباط با ادمین به آیدی زیر پیام دهید:\n@admin_username'),
            ('user_text_allowance','8'),
            ('user_cooldown_hours','2'),
            ('low_text_alert_sent','false'),
            ('website_url',        ''),
            ('website_status',     '1'),
            ('welcome_msg',        'سلام {name} عزیز!\nبه ربات خوش آمدید.'),
            ('twitter_welcome_msg',
             'به پنل محتوای توییتر خوش آمدید.\n'
             'لطفا از منو زیر یک دکمه را انتخاب کنید.\n\n'
             'به دلیل اینکه محتوا را هوش مصنوعی تولید کرده، حتما قبل از اینکه '
             'متن را در توییتر پست کنید، متن را به طور کامل بخوانید.'),
            ('instagram_welcome_msg',
             'به پنل محتوای اینستاگرامی خوش آمدید.\n'
             'لطفا از منوی زیر یک دکمه را انتخاب کنید.'),
            ('reel_limit',            '3'),
            ('reel_cooldown_hours',   '1'),
            ('story_limit',           '3'),
            ('story_cooldown_hours',  '1'),
            ('start_op_msg',       '🚀 عملیات جدید آغاز شد!\nهشتگ فعال: {hashtag}'),
            ('end_op_msg',         'خداقوت\nپایان عملیات {hashtag}'),
            ('lock_msg',           '🚫 دسترسی موقت مسدود شد\n⏳ زمان باقی‌مانده: {time}'),
            ('quick_access_msg', 'برای دریافت سریع محتوا از دکمه‌های زیر استفاده کنید'),
            ('quick_access_enabled', 'true'),
            ('flood_block_msg',
             'شما به دلیل بازیچه گرفتن ربات توسط ربات مسدود شدید.\n'
             'با ادمین ربات ( @zarezade_hastam) پیام بدید تا از مسدودی خارج شوید.'),
        ]
        for k, v in defaults:
            conn.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    # Migration: ستون‌های جدید روی جداول قدیمی
    _migrate()
    ensure_notification_types_seeded()
    ensure_icon_slots_seeded()
    log.info("Database initialised at %s", DB_PATH)


def _migrate():
    migrations = [
        ("user_cooldown", "locked_until", "TEXT DEFAULT NULL"),
        ("user_cooldown", "notified",     "INTEGER DEFAULT 0"),
        ("hashtags",      "is_active",    "INTEGER DEFAULT 0"),
        ("hashtags",      "append_tag",   "INTEGER DEFAULT 1"),
        ("hashtags",      "zone_id",      "INTEGER DEFAULT NULL"),
        ("panel_users",   "password_plain", "TEXT DEFAULT NULL"),
        ("stories",       "media_type",   "TEXT DEFAULT 'photo'"),
        ("photos",        "media_type",   "TEXT DEFAULT 'photo'"),
        # تک‌نشستی (single-session): آخرین توکن/سشنی که این کاربر باهاش وارد
        # شده - چه از سایت چه از اپ. با هر ورود جدید عوض می‌شه و نشست قبلی
        # (هرجا که بود) خودکار نامعتبر می‌شه.
        ("panel_users",   "active_session_token", "TEXT DEFAULT NULL"),
        # ورود با اثر انگشت/چهره/رمز گوشی (سمت اپ/سایت) - این دو ستون فقط
        # برای اطلاع (متادیتا) هستن؛ خودِ اعتبارسنجی بیومتریک روی دستگاه
        # کاربر انجام می‌شه، نه سرور. مالک از همین دو ستون می‌فهمه کاربر
        # کدوم روش رو فعال کرده.
        ("panel_users",   "biometric_enabled", "INTEGER DEFAULT 0"),
        ("panel_users",   "biometric_type",    "TEXT DEFAULT NULL"),
        # قفل پلکانیِ ورود اشتباه: بار اول قفل ۱ ساعته، از بار دوم به بعد
        # هر قفل ۲ ساعته می‌شه. این ستون یادش می‌مونه چندمین باره که این
        # identifier قفل شده (even بعد از باز شدنِ قفل قبلی).
        ("login_attempts", "lock_level", "INTEGER DEFAULT 0"),
        # پشتیبان: کاربری که مالک انتخابش کرده تا به تیکت‌های پشتیبانی
        # جواب بده و گزارش‌های پیام رو ببینه (علاوه بر خودِ مالک).
        ("panel_users",   "is_support", "INTEGER DEFAULT 0"),
        # آیکونی که کاربر برای اپش انتخاب کرده (یکی از ۶ اسلاتِ
        # app_icon_slots) - پیش‌فرض ۱ (همون آیکون اصلی/فعلی).
        ("panel_users",   "chosen_icon_slot", "INTEGER DEFAULT 1"),
        # دسترسیِ این کاربر به سرویس‌ها (اپ/بات/سایت) - یه رشته‌ی
        # جداشده‌با-کاما مثل "app,bot,site". NULL یعنی «از تنظیمِ ناحیه‌ش
        # پیروی کن» (ارثی)؛ ناحیه هم اگه چیزی ست نکرده باشه، یعنی هر سه
        # سرویس آزاده (رفتار قبل از این فیچر، برای سازگاری با گذشته).
        ("panel_users",   "allowed_services", "TEXT DEFAULT NULL"),
        # ردیابیِ پلتفرم و رفتارِ واقعیِ کاربر رویِ محتوایِ دریافتی -
        # platform مشخص می‌کنه از کجا گرفته شده ('app'|'site'|'bot')؛
        # downloaded_at/caption_copied_at فقط برایِ app/site پر می‌شن
        # (چون بات به‌خاطرِ محدودیتِ خودِ تلگرام امکانِ ردیابیِ این دوتا رو
        # نداره - نه یعنی «انجام نشده»، بلکه یعنی «نامشخص»).
        ("content_history", "platform",           "TEXT DEFAULT NULL"),
        ("content_history", "downloaded_at",       "TEXT DEFAULT NULL"),
        ("content_history", "caption_copied_at",   "TEXT DEFAULT NULL"),
        # کدوم panel_user این کاربر رو ساخته (فرمانده‌ی خاص، یا NULL اگه
        # مالک ساخته/از قبل بوده) - پایه‌یِ لازم برایِ سقفِ ساختِ کاربرِ
        # فرمانده‌ها؛ بدونِ این نمی‌شد دقیق شمرد هرکدوم از کاربرها رو کدوم
        # فرمانده ساخته (چون چند فرمانده می‌تونن رویِ یک ناحیه مشترک باشن).
        ("panel_users",   "created_by", "INTEGER DEFAULT NULL"),
        # سقفِ تعدادِ کاربری که این فرمانده مجازه بسازه. NULL = نامحدود.
        ("commanders",    "user_creation_limit", "INTEGER DEFAULT NULL"),
        # ورود مهمان: این کاربرِ پنلی خودکار (بدون یوزرنیم/پسوردِ دستی)
        # از طریقِ دکمه‌ی «ورود مهمان» ساخته شده یا نه.
        ("panel_users",   "is_guest", "INTEGER DEFAULT 0"),
    ]
    with get_conn() as conn:
        for table, col, defn in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
            except Exception:
                pass  # ستون از قبل وجود داشت


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

def get_setting(key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row['value'] if row else None


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))


def get_zone_setting(zone_id, key: str, default=None):
    """
    مقدار یک تنظیم مخصوص یک ناحیه. اگر zone_id=None باشد (ادمین/مالک، یا هنوز
    برای آن ناحیه چیزی تنظیم نشده)، به تنظیم سراسری (settings عمومی) به‌عنوان
    fallback رجوع می‌شود تا رفتار قدیمی حفظ شود.
    """
    if zone_id is not None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM zone_settings WHERE zone_id=? AND key=?", (zone_id, key)
            ).fetchone()
            if row is not None and row['value'] is not None:
                return row['value']
    return get_setting(key) if get_setting(key) is not None else default


def set_zone_setting(zone_id, key: str, value: str):
    if zone_id is None:
        set_setting(key, value)
        return
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO zone_settings (zone_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(zone_id, key) DO UPDATE SET value=excluded.value",
            (zone_id, key, value)
        )


def get_user_zone_id(telegram_user_id: int):
    """zone_id کاربر پنلِ لاگین‌شده با این آیدی تلگرام، یا None اگر پیدا نشد."""
    pu = get_panel_user_by_telegram_id(telegram_user_id)
    return pu['zone_id'] if pu else None


def is_operation_active() -> bool:
    return get_setting('operation_active') == 'true'


def set_operation_active(active: bool):
    set_setting('operation_active', 'true' if active else 'false')


def get_text_allowance(zone_id=None) -> int:
    try:
        return int(get_zone_setting(zone_id, 'user_text_allowance', 8))
    except (ValueError, TypeError):
        return 8


def get_cooldown_hours(zone_id=None) -> int:
    try:
        return int(get_zone_setting(zone_id, 'user_cooldown_hours', 2))
    except (ValueError, TypeError):
        return 2


# ─────────────────────────────────────────────────────────────────────────────
# Website
# ─────────────────────────────────────────────────────────────────────────────

def get_website_url() -> str:       return get_setting('website_url') or ''
def set_website_url(url: str):      set_setting('website_url', url)
def get_website_status() -> bool:   return get_setting('website_status') == '1'
def set_website_status(enabled: bool): set_setting('website_status', '1' if enabled else '0')

def is_guest_login_enabled() -> bool:
    return get_setting('guest_login_enabled') == 'true'
def set_guest_login_enabled(enabled: bool):
    set_setting('guest_login_enabled', 'true' if enabled else 'false')
def get_guest_zone_id():
    v = get_setting('guest_zone_id')
    return int(v) if v else None
def set_guest_zone_id(zone_id):
    set_setting('guest_zone_id', str(zone_id) if zone_id else '')

def is_quick_access_enabled() -> bool:
    return get_setting('quick_access_enabled') != 'false'
def set_quick_access_enabled(enabled: bool):
    set_setting('quick_access_enabled', 'true' if enabled else 'false')


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic messages
# ─────────────────────────────────────────────────────────────────────────────

def get_welcome_msg(zone_id=None) -> str:   return get_zone_setting(zone_id, 'welcome_msg', 'سلام {name} عزیز!')
def set_welcome_msg(t: str, zone_id=None):  set_zone_setting(zone_id, 'welcome_msg', t)
def get_start_op_msg(zone_id=None) -> str:  return get_zone_setting(zone_id, 'start_op_msg', '🚀 عملیات شروع شد!\n\u200cهشتگ: {hashtag}')
def set_start_op_msg(t: str, zone_id=None): set_zone_setting(zone_id, 'start_op_msg', t)
def get_end_op_msg(zone_id=None) -> str:    return get_zone_setting(zone_id, 'end_op_msg', 'پایان عملیات {hashtag}')
def set_end_op_msg(t: str, zone_id=None):   set_zone_setting(zone_id, 'end_op_msg', t)


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

def register_user(user_id: int, username, first_name, last_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?,?,?,?)",
            (user_id, username, first_name, last_name)
        )
        conn.execute(
            "UPDATE users SET username=?, first_name=?, last_name=? WHERE user_id=?",
            (username, first_name, last_name, user_id)
        )


def try_owner_login(user_id: int, login_username: str, login_password: str) -> bool:
    """
    یوزرنیم/پسورد وارد شده (توی چت ربات، دستور /ownerlogin) رو با همون
    یوزرنیم/پسوردی که مالک بار اول توی سایت ساخته مقایسه می‌کنه - یعنی
    دقیقاً همون کلیدهایی که web_app.py توی جدول settings ذخیره می‌کنه
    (site_owner_username / site_owner_password_hash). دیگه هیچ ربطی به
    config.py نداره: یوزرنیم/پسورد مالک، همیشه یک چیز واحده که فقط توی
    سایت (بار اول که بالا میاد) ساخته یا عوض می‌شه.

    در صورت تطابق، user_id (چت‌آیدی عددیِ همیشه-ثابت تلگرام) به‌عنوان
    مالک ربات ذخیره می‌شه (جدول settings، کلید owner_id) و True برمی‌گرده.
    مالک قبلی (اگه بوده) خودکار جایگزین می‌شه - یعنی این هم‌زمان
    مکانیزم «ورود اول» و «انتقال مالکیت» است.
    """
    import logging
    diag = logging.getLogger('bot')

    site_username = get_setting('site_owner_username')
    site_phash = get_setting('site_owner_password_hash')
    if not site_username or not site_phash:
        diag.warning(
            '[owner-login] هنوز هیچ یوزرنیم/پسوردی توی سایت ساخته نشده '
            '(site_owner_username/site_owner_password_hash خالیه) - اول باید '
            'یک بار سایت رو باز کنی و یوزرنیم/پسورد مالک رو اونجا بسازی.'
        )
        return False

    u_in = (login_username or '').strip().lower()
    u_site = site_username.strip().lower()
    p_in = (login_password or '').strip()
    username_ok = (u_in == u_site)
    password_ok = _verify_password(p_in, site_phash)
    # هیچ‌وقت خودِ پسورد رو لاگ نمی‌کنیم؛ فقط طول و نتیجه‌ی مقایسه - همین
    # برای پیدا کردن باگ‌هایی مثل فاصله‌ی اضافه یا یوزرنیم اشتباه کافیه.
    diag.warning(
        '[owner-login] username_match=%s password_match=%s | '
        'len(input_user)=%d len(site_user)=%d len(input_pass)=%d',
        username_ok, password_ok, len(u_in), len(u_site), len(p_in)
    )
    if not username_ok or not password_ok:
        return False
    set_setting('owner_id', str(user_id))
    return True


OWNER_LINK_CODE_TTL_SECONDS = 600  # ۱۰ دقیقه اعتبار کد
# امنیتی: این سقفِ کلِ حدس‌هایِ غلطیه که رویِ یه کدِ فعال قابل قبوله - نه
# به‌ازایِ هر uidِ تلگرام جدا (قبلاً `try_owner_link_code` فقط از طریقِ
# قفلِ per-uid توی handlers_private.py محافظت می‌شد که یعنی یه مهاجم با
# چند اکانتِ یک‌بارمصرفِ تلگرام می‌تونست به‌ازایِ هرکدوم دوباره ۳ حدسِ
# تازه بگیره). با این سقفِ سراسری، بعد از چندتا حدسِ غلط - از هرکسی،
# با هر uidی - خودِ کد بلافاصله باطل می‌شه و مالک باید یکیِ تازه بسازه.
OWNER_LINK_CODE_MAX_ATTEMPTS = 5


def generate_owner_link_code() -> str:
    """
    یه کد ۶ رقمی یک‌بارمصرف می‌سازه که فقط از پنل سایت (وقتی مالک لاگین
    کرده) قابل گرفتنه، و فقط تا ۱۰ دقیقه اعتباره. این جایگزین امن‌تر و
    بدون خطای تایپیِ یوزرنیم/پسورده: چون خودِ کد هر بار تصادفیه و کوتاه
    مدته، حتی اگه لو بره فایده‌ای نداره.
    """
    code = f'{secrets.randbelow(1_000_000):06d}'
    expires_at = int(datetime.utcnow().timestamp()) + OWNER_LINK_CODE_TTL_SECONDS
    set_setting('owner_link_code', code)
    set_setting('owner_link_code_expires', str(expires_at))
    set_setting('owner_link_code_attempts', '0')
    return code


def try_owner_link_code(user_id: int, code: str) -> bool:
    """
    کد وارد شده تو ربات رو با کدی که سایت ساخته مقایسه می‌کنه. در صورت
    تطابق (و عدم انقضا)، user_id به‌عنوان مالک ثبت می‌شه و کد بلافاصله
    باطل می‌شه (یک‌بارمصرف - حتی اگه درست باشه، بار دوم دیگه کار نمی‌کنه).
    """
    stored = get_setting('owner_link_code')
    expires_raw = get_setting('owner_link_code_expires')
    if not stored or not expires_raw:
        return False
    try:
        expires_at = int(expires_raw)
    except (TypeError, ValueError):
        return False
    if int(datetime.utcnow().timestamp()) > expires_at:
        return False
    if (code or '').strip() != stored:
        # حدسِ غلط - شمارنده‌ی سراسریِ همین کد رو زیاد کن؛ اگه از سقف رد
        # شد، خودِ کد رو همین الان (نه فقط بعد از انقضا) باطل کن.
        attempts = int(get_setting('owner_link_code_attempts') or '0') + 1
        set_setting('owner_link_code_attempts', str(attempts))
        if attempts >= OWNER_LINK_CODE_MAX_ATTEMPTS:
            set_setting('owner_link_code', '')
            set_setting('owner_link_code_expires', '0')
        return False
    # کد درست بود - یک‌بارمصرفه، همین الان باطلش کن تا دوباره قابل استفاده نباشه.
    set_setting('owner_link_code', '')
    set_setting('owner_link_code_expires', '0')
    set_setting('owner_link_code_attempts', '0')
    set_setting('owner_id', str(user_id))
    return True


APP_LOCK_CODE_KEY = 'app_lock_code_hash'


def set_app_lock_code(raw_code: str):
    """
    کد باز کردن قفل ماشین‌حساب رو (هش‌شده، مثل پسورد مالک) ذخیره می‌کنه.
    raw_code دقیقاً همون رشته‌ایه که تو ماشین‌حساب تایپ می‌شه (مثلاً "*99*").
    """
    set_setting(APP_LOCK_CODE_KEY, hash_password(raw_code.strip()))


def has_app_lock_code() -> bool:
    return bool(get_setting(APP_LOCK_CODE_KEY))


def verify_app_lock_code(raw_code: str) -> bool:
    stored = get_setting(APP_LOCK_CODE_KEY)
    if not stored:
        return False
    return _verify_password((raw_code or '').strip(), stored)


# محدودیت سبک برای چک کد قفل: حداکثر ۳۰ تلاش تو هر بازه‌ی ۱۰ دقیقه‌ای،
# بعدش فقط ۵ دقیقه خنک‌شدن (نه ساعت‌ها) - چون این می‌تونه با هر ضربه‌ی
# مساوی تو یه ماشین‌حساب واقعی هم صدا زده بشه.
APP_LOCK_RATE_MAX_ATTEMPTS = 30
APP_LOCK_RATE_WINDOW_MINUTES = 10
APP_LOCK_RATE_COOLDOWN_MINUTES = 5


def check_app_lock_rate(identifier: str):
    """برمی‌گردونه (allowed: bool)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM app_lock_attempts WHERE identifier=?", (identifier,)
        ).fetchone()
        now = datetime.utcnow()
        if not row:
            return True
        if row['locked_until']:
            locked_until = datetime.strptime(row['locked_until'], '%Y-%m-%d %H:%M:%S')
            if now < locked_until:
                return False
            conn.execute(
                "UPDATE app_lock_attempts SET attempts=0, window_start=NULL, locked_until=NULL WHERE identifier=?",
                (identifier,)
            )
            return True
        if row['window_start']:
            window_start = datetime.strptime(row['window_start'], '%Y-%m-%d %H:%M:%S')
            if now - window_start > timedelta(minutes=APP_LOCK_RATE_WINDOW_MINUTES):
                conn.execute(
                    "UPDATE app_lock_attempts SET attempts=0, window_start=NULL WHERE identifier=?",
                    (identifier,)
                )
        return True


def record_app_lock_attempt(identifier: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT attempts, window_start FROM app_lock_attempts WHERE identifier=?", (identifier,)
        ).fetchone()
        now = datetime.utcnow()
        now_s = now.strftime('%Y-%m-%d %H:%M:%S')
        if not row:
            conn.execute(
                "INSERT INTO app_lock_attempts (identifier, attempts, window_start) VALUES (?,1,?)",
                (identifier, now_s)
            )
            return
        attempts = (row['attempts'] or 0) + 1
        if attempts >= APP_LOCK_RATE_MAX_ATTEMPTS:
            locked_until = (now + timedelta(minutes=APP_LOCK_RATE_COOLDOWN_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "UPDATE app_lock_attempts SET attempts=0, window_start=NULL, locked_until=? WHERE identifier=?",
                (locked_until, identifier)
            )
        else:
            conn.execute(
                "UPDATE app_lock_attempts SET attempts=? WHERE identifier=?",
                (attempts, identifier)
            )


def get_owner_id():
    """آیدی عددیِ چت مالک ربات، یا None اگه هنوز هیچ‌کس با /ownerlogin و
    یوزرنیم/پسورد درست وارد نشده باشه (مثلاً بلافاصله بعد از نصب تازه)."""
    val = get_setting('owner_id')
    return int(val) if val else None


# ─────────────────────────────────────────────────────────────────────────────
# چند-مالکی از طریقِ تلگرام (owner_accounts) - مالکِ اصلی/اولیه (بالا،
# get_owner_id) دست‌نخورده می‌مونه؛ این‌ها فقط مالک‌هایِ «اضافه»ان که فقط
# با معرفی‌شدنِ آیدیِ تلگرامشون (بدون یوزرنیم/پسورد) تو خودِ بات دسترسیِ
# کاملِ مالک پیدا می‌کنن (نه تو پنل/سایت/اپ - اونجا هنوز لازمه یوزرنیم/
# پسوردِ owner رو داشته باشن، چون اون سمت هویت‌سنجی از راهِ دیگه‌ایه).
# ─────────────────────────────────────────────────────────────────────────────
def add_owner_account(telegram_user_id: int, name: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO owner_accounts (telegram_user_id, name) VALUES (?, ?) "
            "ON CONFLICT(telegram_user_id) DO UPDATE SET name=excluded.name",
            (telegram_user_id, name.strip())
        )


def remove_owner_account(telegram_user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM owner_accounts WHERE telegram_user_id=?", (telegram_user_id,))


def list_owner_accounts() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM owner_accounts ORDER BY added_at"
        ).fetchall()]


def is_extra_owner(telegram_user_id: int) -> bool:
    if telegram_user_id is None:
        return False
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM owner_accounts WHERE telegram_user_id=?", (telegram_user_id,)
        ).fetchone()
        return row is not None


def get_user_by_username_exact(username: str):
    """جستجوی دقیق (case-insensitive) یک یوزرنیم تلگرام در جدول users."""
    uname = username.lstrip('@').strip().lower()
    if not uname:
        return None
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM users WHERE LOWER(username)=? ", (uname,)
        ).fetchall()]


def find_users_by_username(query: str, limit: int = 8) -> list:
    """
    جستجوی یوزرنیم تلگرام برای فلوهای افزودن ادمین/VIP: اول تطابق دقیق
    (case-insensitive)، اگر نبود، شبیه‌ترین یوزرنیم‌ها بر اساس شباهت متن
    برگردانده می‌شود (شبیه‌ترین اول). حداکثر `limit` نتیجه.
    """
    import difflib
    q = query.lstrip('@').strip().lower()
    if not q:
        return []
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT user_id, username, first_name FROM users WHERE username IS NOT NULL AND username != ''"
        ).fetchall()]

    exact = [r for r in rows if r['username'].lower() == q]
    if exact:
        return exact[:limit]

    scored = []
    for r in rows:
        uname = r['username'].lower()
        if q in uname or uname in q:
            score = 0.85 + (len(q) / max(len(uname), 1)) * 0.1
        else:
            score = difflib.SequenceMatcher(None, q, uname).ratio()
        if score >= 0.35:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


def get_all_users() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]


def get_user(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Cooldown
# ─────────────────────────────────────────────────────────────────────────────

def check_cooldown(user_id: int, zone_id=None) -> tuple:
    """
    Returns (remaining_texts, locked_until | None).
    FIX: اگه allowance بالا رفته باشه، کاربر قفل تفاوت رو بگیره.
    """
    allowance  = get_text_allowance(zone_id)
    cooldown_h = get_cooldown_hours(zone_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT texts_sent, locked_until FROM user_cooldown WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if not row:
            return allowance, None

        if row['locked_until']:
            locked_until = datetime.fromisoformat(row['locked_until'])
            if datetime.utcnow() < locked_until:
                # FIX: بررسی allowance جدید — اگه بالا رفته، تفاوت رو بده
                sent = row['texts_sent']
                if sent < allowance:
                    # قفل رو بردار، بذار بقیه رو بگیره
                    conn.execute(
                        "UPDATE user_cooldown SET locked_until=NULL WHERE user_id=?",
                        (user_id,)
                    )
                    return allowance - sent, None
                return 0, locked_until
            # قفل منقضی شده — ریست
            conn.execute(
                "UPDATE user_cooldown SET texts_sent=0, locked_until=NULL, notified=0 WHERE user_id=?",
                (user_id,)
            )
            return allowance, None

        remaining = max(0, allowance - row['texts_sent'])
        if remaining == 0:
            locked_until = (datetime.utcnow() + timedelta(hours=cooldown_h)).isoformat()
            conn.execute(
                "UPDATE user_cooldown SET locked_until=?, notified=0 WHERE user_id=?",
                (locked_until, user_id)
            )
            return 0, datetime.fromisoformat(locked_until)
        return remaining, None


def update_cooldown(user_id: int, add_count: int):
    """
    تجمیع متن‌های دریافتی.
    FIX: texts_sent هنگام قفل ریست نمی‌شه — مقدار واقعی نگه داشته می‌شه.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT texts_sent, locked_until FROM user_cooldown WHERE user_id=?",
            (user_id,)
        ).fetchone()
        now = datetime.utcnow()

        if row and row['locked_until']:
            lu = datetime.fromisoformat(row['locked_until'])
            if now < lu:
                return
            # قفل منقضی — ریست
            conn.execute(
                "UPDATE user_cooldown SET texts_sent=0, locked_until=NULL, notified=0 WHERE user_id=?",
                (user_id,)
            )
            row = None

        new_total  = (row['texts_sent'] if row else 0) + add_count
        allowance  = get_text_allowance()
        cooldown_h = get_cooldown_hours()

        if new_total >= allowance:
            locked_until = (now + timedelta(hours=cooldown_h)).isoformat()
            if row:
                conn.execute(
                    "UPDATE user_cooldown SET texts_sent=?, locked_until=?, notified=0 WHERE user_id=?",
                    (new_total, locked_until, user_id)
                )
            else:
                conn.execute(
                    "INSERT INTO user_cooldown (user_id, texts_sent, locked_until, notified) VALUES (?,?,?,0)",
                    (user_id, new_total, locked_until)
                )
        else:
            if row:
                conn.execute(
                    "UPDATE user_cooldown SET texts_sent=? WHERE user_id=?",
                    (new_total, user_id)
                )
            else:
                conn.execute(
                    "INSERT INTO user_cooldown (user_id, texts_sent, locked_until, notified) VALUES (?,?,NULL,0)",
                    (user_id, new_total)
                )


def get_users_to_notify() -> list:
    with get_conn() as conn:
        now  = datetime.utcnow().isoformat()
        rows = conn.execute(
            "SELECT user_id FROM user_cooldown "
            "WHERE locked_until IS NOT NULL AND locked_until <= ? AND notified=0",
            (now,)
        ).fetchall()
        return [r['user_id'] for r in rows]


def mark_user_notified(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_cooldown SET notified=1 WHERE user_id=?", (user_id,)
        )


# ─────────────────────────────────────────────────────────────────────────────
# رمزنگاری پسورد پنل — PBKDF2-HMAC-SHA256 با salt تصادفی، بدون نیاز به کتابخانه‌ی
# جانبی. فرمت ذخیره: "<salt-hex>$<hash-hex>". هرگز پسورد متن‌ساده ذخیره نمی‌شود.
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Wrapper عمومی برای هش‌کردن پسورد (بدون ذخیره)، مثلا هنگام ثبت‌نام مرحله‌ای."""
    return _hash_password(password)


def _hash_password(password: str, salt: bytes = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200_000)
    return salt.hex() + '$' + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, _ = stored.split('$', 1)
        salt = bytes.fromhex(salt_hex)
    except Exception:
        return False
    return secrets.compare_digest(_hash_password(password, salt), stored)


def generate_random_password(length: int = 8) -> str:
    """پسورد تصادفی ساده و خوانا برای ریست (بدون حروف/ارقام گیج‌کننده مثل 0/O)."""
    alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ─────────────────────────────────────────────────────────────────────────────
# Zones (نواحی)
# ─────────────────────────────────────────────────────────────────────────────

def add_zone(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO zones (name) VALUES (?)", (name,))
        return cur.lastrowid


def get_all_zones() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM zones ORDER BY created_at"
        ).fetchall()]


def get_zone(zone_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM zones WHERE id=?", (zone_id,)).fetchone()
        return dict(row) if row else None


def zone_name_exists(name: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM zones WHERE name=?", (name,)
        ).fetchone() is not None


def delete_zone(zone_id: int):
    """حذف ناحیه به همراه تمام کاربران پنل عضو آن (ON DELETE CASCADE)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM zones WHERE id=?", (zone_id,))


def count_zone_users(zone_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM panel_users WHERE zone_id=?", (zone_id,)
        ).fetchone()
        return row['c'] if row else 0


# ─────────────────────────────────────────────────────────────────────────────
# Panel users (پنل ورود با یوزرنیم/پسورد)
# ─────────────────────────────────────────────────────────────────────────────

def panel_username_exists(username: str) -> bool:
    """بررسی یکتا بودن یوزرنیم — حروف بزرگ/کوچک فرقی نمی‌کنه (case-insensitive)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM panel_users WHERE LOWER(username)=LOWER(?)", (username,)
        ).fetchone() is not None


def create_panel_user(username: str, password: str, zone_id: int, created_by: int | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO panel_users (username, password_hash, password_plain, zone_id, created_by) VALUES (?,?,?,?,?)",
            (username, _hash_password(password), password, zone_id, created_by)
        )
        return cur.lastrowid


def create_guest_login(telegram_user_id: int):
    """یه حساب پنلیِ خودکار و یک‌بارمصرف برایِ مهمان می‌سازه (توی
    ناحیه‌ای که مالک به‌عنوان «ناحیه‌ی مهمان‌ها» ست کرده) و بلافاصله
    بهش لینکش می‌کنه. اگه این تلگرام‌آیدی از قبل حساب پنلیِ لینک‌شده
    داشت (مهمان یا واقعی)، همون رو برمی‌گردونه - یعنی هر کاربر فقط
    یک‌بار می‌تونه مهمون بشه. اگه هنوز ناحیه‌ی مهمان ست نشده، None."""
    existing = get_panel_user_by_telegram_id(telegram_user_id)
    if existing:
        return existing
    zone_id = get_guest_zone_id()
    if not zone_id or not get_zone(zone_id):
        return None
    import secrets
    username = f'guest_{telegram_user_id}_{secrets.token_hex(3)}'
    password = secrets.token_urlsafe(9)
    pu_id = create_panel_user(username, password, zone_id)
    with get_conn() as conn:
        conn.execute("UPDATE panel_users SET is_guest=1 WHERE id=?", (pu_id,))
    mark_panel_login(pu_id, telegram_user_id)
    return get_panel_user_by_username(username)


def create_panel_user_with_hash(username: str, password_hash: str, zone_id: int) -> int:
    """مثل create_panel_user ولی وقتی پسورد از قبل هش شده (مثلا حین ثبت‌نام مرحله‌ای)."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO panel_users (username, password_hash, zone_id) VALUES (?,?,?)",
            (username, password_hash, zone_id)
        )
        return cur.lastrowid


def _generate_unique_username(zone_id: int) -> str:
    """یوزرنیمِ رندومِ یکتا برایِ ساختِ دسته‌ای - پیشوندش از رویِ اسمِ
    ناحیه (فقط حروفِ لاتین/عدد، لوئرکیس) ساخته می‌شه تا از کجا اومدنش
    معلوم باشه، به‌علاوه‌ی یه پسوندِ رندومِ کوتاه برایِ یکتایی. اگه اسمِ
    ناحیه هیچ حرفِ لاتینی نداشت (مثلاً کاملاً فارسیه)، پیشوندِ عمومیِ
    "user" استفاده می‌شه."""
    zone_name = ""
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM zones WHERE id=?", (zone_id,)).fetchone()
        if row:
            zone_name = row["name"] or ""
    prefix = "".join(ch for ch in zone_name.lower() if ch.isascii() and ch.isalnum())[:10]
    if not prefix:
        prefix = "user"
    for _ in range(50):
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(5))
        candidate = f"{prefix}_{suffix}"
        if not panel_username_exists(candidate):
            return candidate
    # اگه با ۵۰ بار تلاش هم به یکتا نرسیدیم (عملاً غیرممکنه)، طولش رو
    # بیشتر می‌کنیم تا فضایِ احتمال به‌قدرِ کافی بزرگ بشه.
    suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(10))
    return f"{prefix}_{suffix}"


def bulk_create_panel_users(zone_id: int, count: int, created_by: int | None = None) -> list[dict]:
    """`count` تا کاربرِ جدید با یوزرنیم/پسوردِ رندوم تو یه ناحیه می‌سازه.
    برمی‌گردونه لیستِ {"id","username","password"} - پسورد همین یه‌بار
    plain برمی‌گرده چون بعدش فقط هش می‌مونه (دقیقاً مثلِ reset_panel_user_password)."""
    out = []
    for _ in range(count):
        uname = _generate_unique_username(zone_id)
        pw = generate_random_password()
        new_id = create_panel_user(uname, pw, zone_id, created_by=created_by)
        out.append({"id": new_id, "username": uname, "password": pw})
    return out


def bulk_import_panel_users(zone_id: int, pairs: list, created_by: int | None = None) -> dict:
    """برایِ ایمپورتِ اکسل: `pairs` لیستی از (username, password) که خودِ
    کاربر داده (نه رندوم). یوزرنیم‌هایِ تکراری یا نامعتبر رد می‌شن، نه
    اینکه کلِ عملیات شکست بخوره - گزارشِ دقیق برمی‌گرده تا فرستنده بفهمه
    دقیقاً چی رد شده و چرا."""
    created, skipped = [], []
    seen_in_batch = set()
    for raw_uname, raw_pw in pairs:
        uname = (raw_uname or "").strip()
        pw = (raw_pw or "").strip()
        if not uname or len(pw) < 4:
            skipped.append({"username": uname or "(خالی)", "reason": "یوزرنیم یا پسورد نامعتبر"})
            continue
        key = uname.lower()
        if key in seen_in_batch:
            skipped.append({"username": uname, "reason": "تکراری در همین فایل"})
            continue
        if panel_username_exists(uname):
            skipped.append({"username": uname, "reason": "از قبل تو دیتابیس هست"})
            continue
        seen_in_batch.add(key)
        new_id = create_panel_user(uname, pw, zone_id, created_by=created_by)
        created.append({"id": new_id, "username": uname})
    return {"created": created, "skipped": skipped}


def get_panel_user(pu_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM panel_users WHERE id=?", (pu_id,)).fetchone()
        return dict(row) if row else None


def get_panel_user_by_username(username: str):
    """جستجوی یوزرنیم پنل — حروف بزرگ/کوچک فرقی نمی‌کنه."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM panel_users WHERE LOWER(username)=LOWER(?)", (username,)
        ).fetchone()
        return dict(row) if row else None


def find_panel_users_by_username(query: str, limit: int = 8) -> list:
    """
    جستجوی یوزرنیم پنل برای فلوهای افزودن ادمین/VIP: اول تطابق دقیق
    (case-insensitive)، اگر نبود، شبیه‌ترین یوزرنیم‌های پنل بر اساس شباهت
    متن برگردانده می‌شود (شبیه‌ترین اول).
    """
    import difflib
    q = query.strip().lower()
    if not q:
        return []
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM panel_users"
        ).fetchall()]

    exact = [r for r in rows if r['username'].lower() == q]
    if exact:
        return exact[:limit]

    scored = []
    for r in rows:
        uname = r['username'].lower()
        if q in uname or uname in q:
            score = 0.85 + (len(q) / max(len(uname), 1)) * 0.1
        else:
            score = difflib.SequenceMatcher(None, q, uname).ratio()
        if score >= 0.35:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


def get_panel_user_by_telegram_id(telegram_user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM panel_users WHERE telegram_user_id=? ORDER BY last_login_at DESC LIMIT 1",
            (telegram_user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_panel_users_by_zone(zone_id: int) -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM panel_users WHERE zone_id=? ORDER BY created_at", (zone_id,)
        ).fetchall()]


def get_all_linked_panel_users() -> list:
    """همه‌ی panel_users که واقعاً وارد حساب‌شون تویِ بات شدن (یعنی
    telegram_user_id دارن) - صرف‌نظر از ناحیه. برایِ پیام‌هایِ خودکارِ
    عمومی (مثلِ شروع/پایانِ عملیات بدون ناحیه‌ی خاص) باید از همینجا
    استفاده بشه، نه از `get_all_users()` (که شاملِ هرکسی می‌شه که فقط
    یه‌بار /start زده، حتی اگه هنوز وارد حسابش نشده و وضعیتش/دسترسیش
    اصلاً معلوم نیست)."""
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM panel_users WHERE telegram_user_id IS NOT NULL"
        ).fetchall()]


def get_all_panel_users() -> list:
    """همه‌یِ panel_users، صرف‌نظر از ناحیه - برایِ اکسپورتِ کاملِ اکسل
    (فازِ ۵) لازمه؛ قبلاً فقط نسخه‌یِ per-zone (`get_panel_users_by_zone`)
    یا per-telegram-link (`get_all_linked_panel_users`) وجود داشت."""
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM panel_users ORDER BY zone_id, created_at"
        ).fetchall()]


def get_export_rows(zone_id: int | None = None, zone_ids: list[int] | None = None) -> list:
    """ردیف‌هایِ آماده برایِ اکسپورتِ اکسل (فازِ ۵) - هر ردیف همه‌یِ
    نقش‌هایِ کاربر رو یه‌جا داره (VIP توییتر/اینستا، سرپرست، فرمانده) تا
    تویِ اکسل مجبور نباشی چندتا لیستِ جدا رو با هم تطبیق بدی.
    zone_id=None و zone_ids=None یعنی همه‌یِ ناحیه‌ها. zone_ids (فازِ ۸)
    برایِ اکسپورتِ هم‌زمانِ چند ناحیه‌ی مشخص (نه همه، نه فقط یکی)."""
    if zone_ids:
        users = []
        for zid in zone_ids:
            users.extend(get_panel_users_by_zone(zid))
    elif zone_id:
        users = get_panel_users_by_zone(zone_id)
    else:
        users = get_all_panel_users()
    zone_names = {z["id"]: z["name"] for z in get_all_zones()}
    commander_ids = {c["id"] for c in get_all_commanders()}
    rows = []
    for u in users:
        tid = u.get("telegram_user_id")
        rows.append({
            "id": u["id"],
            "username": u["username"],
            "password": u.get("password_plain"),
            "zone_name": zone_names.get(u["zone_id"], "؟"),
            "display_name": u.get("display_name") or "",
            "telegram_linked": bool(tid),
            "is_vip_twitter": bool(tid) and is_vip_user(tid),
            "is_vip_instagram": bool(tid) and is_instagram_vip_user(tid),
            "is_supervisor": is_supervisor(u["id"]),
            "is_commander": u["id"] in commander_ids,
            "created_at": u.get("created_at") or "",
        })
    return rows


def get_zones_export_rows() -> list:
    """ردیف‌هایِ آماده برایِ اکسپورتِ «لیستِ ناحیه‌ها» - تعدادِ کاربر و
    اسمِ فرمانده(هایِ) هرکدوم."""
    commanders_by_zone: dict = {}
    for c in get_all_commanders():
        for zid in c["zone_ids"]:
            commanders_by_zone.setdefault(zid, []).append(c["username"])
    rows = []
    for z in get_all_zones():
        rows.append({
            "name": z["name"],
            "user_count": count_zone_users(z["id"]),
            "commander_usernames": "، ".join(commanders_by_zone.get(z["id"], [])) or "—",
            "created_at": z.get("created_at") or "",
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# محدودیت تلاش ورود اشتباه (Brute-force protection) — چه از ربات چه از سایت
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# محدودیت تلاش ورود اشتباه (Brute-force protection) — چه از ربات چه از سایت
#
# قانون دقیق (طبق خواسته): بعد از ۳ تلاش اشتباه پشت‌سرهم، ۱ ساعت قفل.
# اگه بعد از باز شدن اون قفل، دوباره ۳ بار اشتباه زد، این‌بار ۲ ساعت قفل.
# از اون به بعد، هر ۳ بار اشتباهِ دیگه، همیشه ۲ ساعت قفل می‌شه.
# ─────────────────────────────────────────────────────────────────────────────
LOGIN_MAX_ATTEMPTS   = 3
LOGIN_LOCK_MINUTES_FIRST = 60    # ساعت اول قفل
LOGIN_LOCK_MINUTES_NEXT  = 120   # قفل‌های بعدی

def check_login_lock(identifier: str):
    """
    برمی‌گردونه (allowed: bool, locked_until: str|None). اگه قفل شده باشه
    ولی زمانش گذشته باشه، خودش قفل رو باز می‌کنه (attempts صفر می‌شه، ولی
    lock_level نگه داشته می‌شه تا دفعه‌ی بعد پلکان درست حساب بشه).
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM login_attempts WHERE identifier=?", (identifier,)
        ).fetchone()
        if not row or not row['locked_until']:
            return True, None
        locked_until = datetime.strptime(row['locked_until'], '%Y-%m-%d %H:%M:%S')
        if datetime.utcnow() >= locked_until:
            conn.execute(
                "UPDATE login_attempts SET attempts=0, locked_until=NULL WHERE identifier=?",
                (identifier,)
            )
            return True, None
        return False, row['locked_until']


def record_failed_login(identifier: str):
    """یک تلاش ناموفق ثبت می‌کنه؛ بعد از هر LOGIN_MAX_ATTEMPTS بار، طبق
    پلکان (۱ ساعت → ۲ ساعت → ۲ ساعت → ...) قفل می‌کنه."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT attempts, lock_level FROM login_attempts WHERE identifier=?", (identifier,)
        ).fetchone()
        attempts = (row['attempts'] if row else 0) + 1
        lock_level = row['lock_level'] if row else 0
        locked_until = None
        if attempts >= LOGIN_MAX_ATTEMPTS:
            lock_level += 1
            minutes = LOGIN_LOCK_MINUTES_FIRST if lock_level == 1 else LOGIN_LOCK_MINUTES_NEXT
            locked_until = (datetime.utcnow() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
            attempts = 0  # با شروع قفل جدید، شمارشگر برای دور بعد صفر می‌شه
        conn.execute(
            "INSERT INTO login_attempts (identifier, attempts, locked_until, lock_level) VALUES (?,?,?,?) "
            "ON CONFLICT(identifier) DO UPDATE SET attempts=excluded.attempts, "
            "locked_until=excluded.locked_until, lock_level=excluded.lock_level",
            (identifier, attempts, locked_until, lock_level)
        )
        return attempts, locked_until


def record_successful_login(identifier: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM login_attempts WHERE identifier=?", (identifier,))


# ─────────────────────────────────────────────────────────────────────────────
# نوتیفیکیشن پوش - انواعِ سیستمی + توکن‌ها
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_NOTIFICATION_TYPES = [
    ("chat_message",      "پیام جدید چت",         "{sender_name} توی «{group_name}» پیام داد: {preview}"),
    ("chat_reply",        "ریپلای به پیامت",       "{sender_name} به پیامت جواب داد: {preview}"),
    ("chat_mention",      "منشن شدن",              "{sender_name} توی «{group_name}» تو را منشن کرد: {preview}"),
    ("chat_important",    "پیامِ مهم",             "📢 {group_name}: {preview}"),
    ("group_added",       "اضافه شدن به گروه",     "به گروه «{group_name}» اضافه شدی."),
    ("operation_start",   "شروع عملیات",           "🚀 عملیات شروع شد. هشتگ فعال: {hashtag}"),
    ("operation_stop",    "پایان عملیات",          "🛑 عملیات متوقف شد ({hashtag})."),
    ("content_text",      "متن جدید موجود شد",     "📝 متن تازه برای هشتگ «{hashtag}» اضافه شد."),
    ("content_photo",     "عکس جدید موجود شد",     "🖼 عکس تازه برای هشتگ «{hashtag}» اضافه شد."),
    ("content_reel",      "ریلز جدید موجود شد",    "🎬 ریلز تازه برای هشتگ «{hashtag}» اضافه شد."),
    ("content_story",     "استوری جدید موجود شد",  "📸 استوری تازه برای هشتگ «{hashtag}» اضافه شد."),
    ("rate_limit_lifted", "رفع محدودیت",           "🎉 محدودیتت رفع شد، می‌تونی دوباره محتوا بگیری."),
    ("new_device_login",  "ورود از دستگاه دیگه",   "⚠️ حسابت از یه دستگاه/مرورگر دیگه وارد شد و همینجا خارج شدی."),
    ("account_locked",    "قفل شدن حساب",          "🚫 به‌خاطر تلاش‌های ورود اشتباه، حسابت موقتاً قفل شد."),
    ("permission_changed", "تغییر دسترسی‌هات",     "🔧 دسترسی‌هات توی «{group_name}» تغییر کرد: {summary}"),
]


def ensure_notification_types_seeded():
    with get_conn() as conn:
        for key, title, template in DEFAULT_NOTIFICATION_TYPES:
            conn.execute(
                "INSERT OR IGNORE INTO notification_types (key, title, template, enabled) VALUES (?,?,?,1)",
                (key, title, template)
            )


def ensure_icon_slots_seeded():
    """فازِ ۳۱-الف: فقط ۲ اسلاتِ آیکونِ اپ (طبقِ تصمیم - لانچرآیکونِ اپ
    رویِ گوشی باید فقط ۲تا باشه: تیره/نارنجی و سفید/نارنجی؛ قبلاً ۶تا
    بود). اسلات‌هایِ ۳ تا ۶ که از نسخه‌های قبلی تو دیتابیس مونده بودن
    این‌جا صراحتاً غیرفعال می‌شن، چون تو AndroidManifestِ جدید اون
    alias‌ها اصلاً وجود ندارن و انتخابشون از سمتِ کاربر هیچ اثری رو
    گوشی نداره."""
    with get_conn() as conn:
        labels = {1: "آیکونِ تیره", 2: "آیکونِ روشن"}
        for i in (1, 2):
            conn.execute(
                "INSERT OR IGNORE INTO app_icon_slots (id, label, enabled, all_zones) VALUES (?,?,1,1)",
                (i, labels[i]),
            )
        conn.execute("UPDATE app_icon_slots SET enabled=0 WHERE id > 2")


def get_icon_slots():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM app_icon_slots ORDER BY id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            zrows = conn.execute(
                "SELECT zone_id FROM app_icon_slot_zones WHERE icon_slot_id=?", (r["id"],)
            ).fetchall()
            d["zone_ids"] = [z["zone_id"] for z in zrows]
            out.append(d)
        return out


def get_available_icon_slots(zone_id):
    """اسلات‌های فعالی که این ناحیه بهشون دسترسی داره (all_zones=1 یا
    zone_id صراحتاً تو لیست مجازها باشه)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM app_icon_slots WHERE enabled=1 ORDER BY id").fetchall()
        out = []
        for r in rows:
            if r["all_zones"]:
                out.append(dict(r))
                continue
            allowed = conn.execute(
                "SELECT 1 FROM app_icon_slot_zones WHERE icon_slot_id=? AND zone_id=?", (r["id"], zone_id)
            ).fetchone()
            if allowed:
                out.append(dict(r))
        return out


def set_icon_slot_config(slot_id, label=None, enabled=None, all_zones=None, zone_ids=None):
    with get_conn() as conn:
        if label is not None:
            conn.execute("UPDATE app_icon_slots SET label=? WHERE id=?", (label, slot_id))
        if enabled is not None:
            conn.execute("UPDATE app_icon_slots SET enabled=? WHERE id=?", (1 if enabled else 0, slot_id))
        if all_zones is not None:
            conn.execute("UPDATE app_icon_slots SET all_zones=? WHERE id=?", (1 if all_zones else 0, slot_id))
        if zone_ids is not None:
            conn.execute("DELETE FROM app_icon_slot_zones WHERE icon_slot_id=?", (slot_id,))
            for zid in zone_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO app_icon_slot_zones (icon_slot_id, zone_id) VALUES (?,?)", (slot_id, zid)
                )


def set_icon_slot_preview(slot_id, preview_path):
    with get_conn() as conn:
        conn.execute("UPDATE app_icon_slots SET preview_path=? WHERE id=?", (preview_path, slot_id))


def get_user_chosen_icon(panel_user_id) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT chosen_icon_slot FROM panel_users WHERE id=?", (panel_user_id,)).fetchone()
    return (row["chosen_icon_slot"] if row and row["chosen_icon_slot"] else 1)


def set_user_chosen_icon(panel_user_id, slot_id):
    with get_conn() as conn:
        conn.execute("UPDATE panel_users SET chosen_icon_slot=? WHERE id=?", (slot_id, panel_user_id))


ALL_SERVICES = {"app", "bot", "site"}


def _parse_services(raw: str | None):
    """None یعنی «اصلاً چیزی ست نشده» (باید ارث ببره/پیش‌فرض بگیره).
    یه رشته‌ی خالی یا فقط شامل مقادیرِ نامعتبر یعنی «صراحتاً هیچ سرویسی
    مجاز نیست» (نتیجه‌ش یه‌ست خالیه، نه None) - این دو باید فرق داشته
    باشن، وگرنه بستنِ کاملِ دسترسیِ یه کاربر اشتباهی به «آزاد» تبدیل می‌شه."""
    if raw is None:
        return None
    parts = {p.strip() for p in raw.split(",") if p.strip()}
    return parts & ALL_SERVICES


def get_zone_allowed_services(zone_id) -> set:
    """دسترسیِ سرویس‌های یه ناحیه. اگه چیزی ست نشده باشه یعنی هر سه سرویس
    آزادن (رفتارِ قبل از این فیچر، برای سازگاری با ناحیه‌های قدیمی)."""
    parsed = _parse_services(get_zone_setting(zone_id, "allowed_services", None))
    return parsed if parsed is not None else set(ALL_SERVICES)


def set_zone_allowed_services(zone_id, services: set):
    set_zone_setting(zone_id, "allowed_services", ",".join(sorted(services & ALL_SERVICES)))


def get_user_allowed_services(panel_user_id) -> set:
    """دسترسیِ مؤثرِ نهاییِ یه کاربر: اول تنظیمِ خودِ کاربر (اگه ست شده،
    حتی اگه یه‌ست خالی/صراحتاً-هیچی باشه)، وگرنه تنظیمِ ناحیه‌ش، وگرنه
    همه‌چیز آزاد (رفتارِ قدیمی)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT allowed_services, zone_id FROM panel_users WHERE id=?", (panel_user_id,)
        ).fetchone()
    if not row:
        return set(ALL_SERVICES)
    own = _parse_services(row["allowed_services"])
    if own is not None:
        return own
    return get_zone_allowed_services(row["zone_id"])


def user_has_service_access(panel_user_id, service: str) -> bool:
    return service in get_user_allowed_services(panel_user_id)


def set_user_allowed_services(panel_user_id, services: set | None):
    """services=None یعنی برگرد به حالتِ «ارثی از ناحیه» (پاک‌کردنِ
    override)؛ یه‌ستِ خالی یعنی صراحتاً از همه‌چیز محرومش کن."""
    value = None if services is None else ",".join(sorted(services & ALL_SERVICES))
    with get_conn() as conn:
        conn.execute("UPDATE panel_users SET allowed_services=? WHERE id=?", (value, panel_user_id))


def get_access_denied_msg(zone_id=None) -> str:
    return get_zone_setting(zone_id, "access_denied_msg", "⛔️ دسترسی نداری.")


def set_access_denied_msg(text: str, zone_id=None):
    set_zone_setting(zone_id, "access_denied_msg", text)


def get_notification_types():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM notification_types ORDER BY key").fetchall()
        return [dict(r) for r in rows]


def get_user_notification_pref(panel_user_id: int, notif_key: str) -> bool:
    """پیش‌فرض روشنه؛ فقط اگه کاربر صراحتاً خاموش کرده باشه False برمی‌گرده."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT enabled FROM user_notification_prefs WHERE panel_user_id=? AND notif_key=?",
            (panel_user_id, notif_key),
        ).fetchone()
    return bool(row["enabled"]) if row else True


def set_user_notification_pref(panel_user_id: int, notif_key: str, enabled: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_notification_prefs (panel_user_id, notif_key, enabled) VALUES (?,?,?) "
            "ON CONFLICT(panel_user_id, notif_key) DO UPDATE SET enabled=excluded.enabled",
            (panel_user_id, notif_key, 1 if enabled else 0),
        )


def get_user_notification_prefs(panel_user_id: int) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT notif_key, enabled FROM user_notification_prefs WHERE panel_user_id=?",
            (panel_user_id,),
        ).fetchall()
    return {r["notif_key"]: bool(r["enabled"]) for r in rows}


def get_notification_type(key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM notification_types WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None


def set_notification_type(key: str, enabled: bool = None, template: str = None):
    with get_conn() as conn:
        if enabled is not None:
            conn.execute("UPDATE notification_types SET enabled=? WHERE key=?", (1 if enabled else 0, key))
        if template is not None:
            conn.execute("UPDATE notification_types SET template=? WHERE key=?", (template, key))


def is_notification_enabled(key: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT enabled FROM notification_types WHERE key=?", (key,)).fetchone()
        return bool(row["enabled"]) if row else False


def save_push_token(role: str, panel_user_id, token: str, platform: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO push_tokens (role, panel_user_id, token, platform) VALUES (?,?,?,?) "
            "ON CONFLICT(token) DO UPDATE SET role=excluded.role, panel_user_id=excluded.panel_user_id, platform=excluded.platform",
            (role, panel_user_id, token, platform)
        )


def delete_push_token(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM push_tokens WHERE token=?", (token,))


def get_push_tokens_for(role: str, panel_user_id=None) -> list:
    with get_conn() as conn:
        if role == "owner":
            rows = conn.execute("SELECT token FROM push_tokens WHERE role='owner'").fetchall()
        else:
            rows = conn.execute(
                "SELECT token FROM push_tokens WHERE role='friend' AND panel_user_id=?", (panel_user_id,)
            ).fetchall()
        return [r["token"] for r in rows]


def get_push_tokens_for_zone(zone_id) -> list:
    """توکن‌های همه‌ی کاربرهای یک ناحیه (یا همه‌ی کاربرها اگه zone_id=None)."""
    with get_conn() as conn:
        if zone_id is None:
            rows = conn.execute("SELECT token FROM push_tokens WHERE role='friend'").fetchall()
        else:
            rows = conn.execute(
                "SELECT pt.token FROM push_tokens pt JOIN panel_users pu ON pu.id = pt.panel_user_id "
                "WHERE pt.role='friend' AND pu.zone_id=?", (zone_id,)
            ).fetchall()
        return [r["token"] for r in rows]


def get_push_tokens_for_zone_by_user(zone_id) -> list:
    """مثلِ get_push_tokens_for_zone ولی panel_user_id رو هم برمی‌گردونه
    (به‌صورتِ لیستی از (panel_user_id, token)) - برایِ notify_zone که باید
    قبل از فرستادن، ترجیحِ شخصیِ هر کاربر برایِ اون notif_key رو چک کنه.
    خودِ get_push_tokens_for_zone دست‌نخورده موند چون send_custom
    (پیامِ دستیِ مالک، بدونِ notif_key) نیازی به این فیلتر نداره."""
    with get_conn() as conn:
        if zone_id is None:
            rows = conn.execute(
                "SELECT panel_user_id, token FROM push_tokens WHERE role='friend'"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT pt.panel_user_id, pt.token FROM push_tokens pt JOIN panel_users pu ON pu.id = pt.panel_user_id "
                "WHERE pt.role='friend' AND pu.zone_id=?", (zone_id,)
            ).fetchall()
        return [(r["panel_user_id"], r["token"]) for r in rows]


def should_notify_content(hashtag_id: int, kind: str, debounce_minutes: int = 15) -> bool:
    """طبق دیبانس: فقط اگه از آخرین‌باری که برای این هشتگ+نوع نوتیف
    فرستادیم، بیشتر از debounce_minutes گذشته باشه، True برمی‌گردونه (و
    خودش last_sent رو هم آپدیت می‌کنه) - تا افزودن دسته‌جمعیِ آیتم‌ها
    باعث اسپم نشه."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_sent FROM content_notify_debounce WHERE hashtag_id=? AND kind=?", (hashtag_id, kind)
        ).fetchone()
        now = datetime.utcnow()
        if row:
            last = datetime.strptime(row["last_sent"], '%Y-%m-%d %H:%M:%S')
            if (now - last).total_seconds() < debounce_minutes * 60:
                return False
        conn.execute(
            "INSERT INTO content_notify_debounce (hashtag_id, kind, last_sent) VALUES (?,?,?) "
            "ON CONFLICT(hashtag_id, kind) DO UPDATE SET last_sent=excluded.last_sent",
            (hashtag_id, kind, now.strftime('%Y-%m-%d %H:%M:%S'))
        )
        return True


def verify_panel_login(username: str, password: str):
    """در صورت درست بودن یوزرنیم/پسورد، رکورد کاربر را برمی‌گرداند وگرنه None."""
    user = get_panel_user_by_username(username)
    if not user:
        return None
    if not _verify_password(password, user['password_hash']):
        return None
    return user


def mark_panel_login(pu_id: int, telegram_user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE panel_users SET telegram_user_id=?, last_login_at=datetime('now') WHERE id=?",
            (telegram_user_id, pu_id)
        )


# ─────────────────────────────────────────────────────────────────────────────
# تک‌نشستی (single active session) - چه از سایت چه از اپ، برای کاربران پنل
# (نه مالک - مالک از این محدودیت مستثناست).
# ─────────────────────────────────────────────────────────────────────────────
def set_active_session_token(pu_id: int, token: str | None):
    with get_conn() as conn:
        conn.execute("UPDATE panel_users SET active_session_token=? WHERE id=?", (token, pu_id))


def get_active_session_token(pu_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT active_session_token FROM panel_users WHERE id=?", (pu_id,)).fetchone()
        return row["active_session_token"] if row else None


# ─────────────────────────────────────────────────────────────────────────────
# بیومتریک (اثر انگشت/چهره/رمز گوشی) - فقط متادیتا برای دید مالک؛ خودِ
# احرازهویت روی دستگاه کاربر انجام می‌شه.
# ─────────────────────────────────────────────────────────────────────────────
def set_panel_user_biometric(pu_id: int, enabled: bool, biometric_type: str | None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE panel_users SET biometric_enabled=?, biometric_type=? WHERE id=?",
            (1 if enabled else 0, biometric_type if enabled else None, pu_id)
        )


def panel_logout(telegram_user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE panel_users SET telegram_user_id=NULL WHERE telegram_user_id=?",
            (telegram_user_id,)
        )


def reset_panel_user_password(pu_id: int) -> str:
    """پسورد تصادفی جدید می‌سازد، هش‌شده + متن‌ساده ذخیره می‌کند و همون رو برمی‌گرداند."""
    new_pw = generate_random_password()
    with get_conn() as conn:
        conn.execute(
            "UPDATE panel_users SET password_hash=?, password_plain=? WHERE id=?",
            (_hash_password(new_pw), new_pw, pu_id)
        )
    revoke_all_tokens_for_user(pu_id)
    return new_pw


def set_panel_user_password(pu_id: int, new_password: str):
    """تنظیم دستی پسورد یک کاربر پنل (مثلا وقتی مالک خودش پسورد دلخواه می‌ذاره)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE panel_users SET password_hash=?, password_plain=? WHERE id=?",
            (_hash_password(new_password), new_password, pu_id)
        )
    revoke_all_tokens_for_user(pu_id)


def delete_panel_user(pu_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM panel_users WHERE id=?", (pu_id,))


# ─────────────────────────────────────────────────────────────────────────────
# توکن‌های API — برای کلاینت‌هایی مثل اپ موبایل که کوکی/سشن ندارن
# ─────────────────────────────────────────────────────────────────────────────

def create_api_token(pu_id: int) -> str:
    token = secrets.token_hex(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_tokens (token, panel_user_id) VALUES (?,?)",
            (token, pu_id)
        )
    return token


def get_panel_user_by_token(token: str):
    """اگه توکن معتبر بود، رکورد کاربر پنل رو برمی‌گردونه (و last_used_at رو به‌روز می‌کنه)."""
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT panel_user_id FROM api_tokens WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE api_tokens SET last_used_at=datetime('now') WHERE token=?", (token,)
        )
        pu = conn.execute(
            "SELECT * FROM panel_users WHERE id=?", (row['panel_user_id'],)
        ).fetchone()
        return dict(pu) if pu else None


def revoke_api_token(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM api_tokens WHERE token=?", (token,))


def revoke_all_tokens_for_user(pu_id: int):
    """موقع ریست پسورد صدا زده می‌شه — همه‌ی نشست‌های اپ اون کاربر باطل می‌شن."""
    with get_conn() as conn:
        conn.execute("DELETE FROM api_tokens WHERE panel_user_id=?", (pu_id,))


# ─────────────────────────────────────────────────────────────────────────────
# سرپرست‌ها (افراد) — panel_user هایی که اجازه دارن رمز کاربران یک یا چند
# ناحیه رو ببینن (علاوه بر دسترسی عادی محتوایشون).
# ─────────────────────────────────────────────────────────────────────────────

def set_supervisor_zones(pu_id: int, zone_ids: list):
    """جایگزین کردن کامل لیست ناحیه‌هایی که این فرد سرپرستشونه. لیست خالی = حذف نقش."""
    with get_conn() as conn:
        conn.execute("DELETE FROM supervisor_zones WHERE panel_user_id=?", (pu_id,))
        for zid in set(zone_ids):
            conn.execute(
                "INSERT OR IGNORE INTO supervisor_zones (panel_user_id, zone_id) VALUES (?,?)",
                (pu_id, zid)
            )


def get_supervisor_zone_ids(pu_id: int) -> list:
    with get_conn() as conn:
        return [r['zone_id'] for r in conn.execute(
            "SELECT zone_id FROM supervisor_zones WHERE panel_user_id=?", (pu_id,)
        ).fetchall()]


def is_supervisor(pu_id: int) -> bool:
    return len(get_supervisor_zone_ids(pu_id)) > 0


def remove_supervisor(pu_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM supervisor_zones WHERE panel_user_id=?", (pu_id,))


def get_all_supervisors() -> list:
    """همه‌ی panel_user هایی که حداقل یک ناحیه سرپرستی دارن، به همراه لیست ناحیه‌هاشون."""
    with get_conn() as conn:
        pu_ids = [r['panel_user_id'] for r in conn.execute(
            "SELECT DISTINCT panel_user_id FROM supervisor_zones"
        ).fetchall()]
        result = []
        for pid in pu_ids:
            pu = conn.execute("SELECT * FROM panel_users WHERE id=?", (pid,)).fetchone()
            if not pu:
                continue
            zones = conn.execute(
                "SELECT z.id, z.name FROM zones z JOIN supervisor_zones sz ON sz.zone_id=z.id "
                "WHERE sz.panel_user_id=?", (pid,)
            ).fetchall()
            result.append({**dict(pu), 'zones': [dict(z) for z in zones]})
        return result


def get_supervised_panel_users(pu_id: int) -> list:
    """
    همه‌ی کاربران پنلِ ناحیه‌هایی که این فرد سرپرستشونه (خود سرپرست حذف نمی‌شه
    از لیست اگر تصادفاً عضو همون ناحیه هم باشه — چون داره اطلاعات خودش رو هم
    می‌بینه که اشکالی نداره)، همراه با نام ناحیه.
    """
    zone_ids = get_supervisor_zone_ids(pu_id)
    if not zone_ids:
        return []
    with get_conn() as conn:
        placeholders = ','.join('?' * len(zone_ids))
        rows = conn.execute(
            f"SELECT pu.*, z.name as zone_name FROM panel_users pu "
            f"JOIN zones z ON z.id = pu.zone_id "
            f"WHERE pu.zone_id IN ({placeholders}) ORDER BY z.name, pu.username",
            zone_ids
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# فرمانده‌ها (افراد): یک panel_user که مالک بهش اختیارِ مدیریتیِ محدود روی یک
# یا چند ناحیه‌ی مشخص داده - با یه چک‌لیستِ ریزدانه از اینکه دقیقاً چیکار حق
# داره بکنه. برخلافِ سرپرست (که فقط می‌تونه رمز ببینه)، فرمانده می‌تونه واقعاً
# کاربر اضافه/حذف کنه، پروفایل عوض کنه، دسترسی سرویس تغییر بده، و (اگه اجازه
# داشته باشه) ناحیه‌ی جدید بسازه.
# ─────────────────────────────────────────────────────────────────────────────

# کاتالوگِ کاملِ مجوزهای قابل‌واگذاری، دسته‌بندی‌شده - این تنها منبعِ حقیقتِ
# «چه مجوزهایی وجود دارن» است؛ هم بک‌اند (چک‌کردنِ دسترسی) و هم endpointِ
# GET /api/admin/commander-permission-catalog (که اپِ فلاتر ازش چک‌باکس‌ها رو
# می‌سازه) از همینجا می‌خونن - یعنی برای اضافه‌کردنِ یه مجوزِ جدید، فقط باید
# اینجا یه خط اضافه کنی و یه چک به endpointِ مربوطه، نه دستکاریِ اسکیما.
# سنتینلِ داخلی برایِ set_commander: چون None خودش یه مقدارِ معنادار
# («نامحدود») هست، نمی‌شه از None به‌عنوانِ «چیزی داده نشده» هم استفاده
# کرد - این آبجکتِ یکتا برایِ تشخیصِ «پارامتر اصلاً پاس داده نشده» است.
_UNSET = object()

COMMANDER_PERMISSIONS = {
    "zones": {
        "label": "ناحیه‌ها",
        "perms": {
            "zone.create": "ساختنِ ناحیه‌ی جدید",
        },
    },
    "users": {
        "label": "کاربرها (فقط داخلِ ناحیه‌های تحتِ فرماندهی‌ش)",
        "perms": {
            "user.add": "افزودنِ کاربرِ جدید",
            "user.remove": "حذفِ کاربر",
            "user.view_credentials": "دیدنِ یوزرنیم و پسوردِ کاربرها",
            "user.reset_password": "ریست‌کردنِ پسوردِ کاربر",
            "user.edit_profile": "ویرایشِ مشخصاتِ کاربر (نامِ نمایشی و مشابه)",
            "user.change_service_access": "تغییرِ دسترسیِ سرویس‌هایِ کاربر (app/bot/site)",
        },
    },
}


def _all_commander_perm_keys() -> set:
    return {k for cat in COMMANDER_PERMISSIONS.values() for k in cat["perms"]}


def set_commander(pu_id: int, zone_ids: list, perm_keys: list, creation_limit=_UNSET):
    """جایگزینِ کاملِ نقشِ فرمانده برای یک panel_user: لیستِ ناحیه‌ها و
    لیستِ مجوزها رو کامل عوض می‌کنه (نه اضافه‌کردنِ تدریجی). زون‌های خالی
    یا مجوزهای خالی مشکلی نداره (یعنی فرمانده‌ست ولی فعلاً هیچ اختیاری نداره).
    creation_limit: اگه داده نشه (پیش‌فرض _UNSET)، مقدارِ فعلی دست‌نخورده
    می‌مونه؛ عددِ صحیح یعنی سقفِ ساختِ کاربر؛ None صراحتاً یعنی نامحدود."""
    valid_perms = _all_commander_perm_keys()
    perm_keys = [p for p in perm_keys if p in valid_perms]
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO commanders (panel_user_id) VALUES (?)", (pu_id,))
        if creation_limit is not _UNSET:
            conn.execute(
                "UPDATE commanders SET user_creation_limit=? WHERE panel_user_id=?",
                (creation_limit, pu_id)
            )
        conn.execute("DELETE FROM commander_zones WHERE panel_user_id=?", (pu_id,))
        for zid in set(zone_ids):
            conn.execute(
                "INSERT OR IGNORE INTO commander_zones (panel_user_id, zone_id) VALUES (?,?)",
                (pu_id, zid)
            )
        conn.execute("DELETE FROM commander_permissions WHERE panel_user_id=?", (pu_id,))
        for pk in set(perm_keys):
            conn.execute(
                "INSERT OR IGNORE INTO commander_permissions (panel_user_id, perm_key) VALUES (?,?)",
                (pu_id, pk)
            )


def get_commander_creation_limit(pu_id: int):
    """سقفِ ساختِ کاربرِ این فرمانده. None = نامحدود (یا اصلاً فرمانده
    نیست - در اون حالت هم منطقی‌ست که محدودیتی گزارش نشه)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_creation_limit FROM commanders WHERE panel_user_id=?", (pu_id,)
        ).fetchone()
    return row["user_creation_limit"] if row else None


def count_users_created_by(pu_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM panel_users WHERE created_by=?", (pu_id,)
        ).fetchone()
    return row["c"] if row else 0


def commander_can_create_users(pu_id: int, additional: int = 1) -> bool:
    """آیا این فرمانده اجازه داره `additional` تا کاربرِ دیگه بسازه؟
    (برایِ ساختِ دسته‌ای، additional بزرگ‌تر از ۱ هم می‌تونه باشه - چک
    باید قبل از ساختن انجام بشه، نه بعدش که خیلی دیر شده)."""
    limit = get_commander_creation_limit(pu_id)
    if limit is None:
        return True
    return count_users_created_by(pu_id) + additional <= limit


def remove_commander(pu_id: int):
    """حذفِ کاملِ نقشِ فرمانده (زون‌ها و مجوزهاش هم با CASCADE پاک می‌شن،
    ولی صراحتاً هم پاک می‌کنیم که وابسته به CASCADE نباشیم)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM commander_permissions WHERE panel_user_id=?", (pu_id,))
        conn.execute("DELETE FROM commander_zones WHERE panel_user_id=?", (pu_id,))
        conn.execute("DELETE FROM commanders WHERE panel_user_id=?", (pu_id,))


def is_commander(pu_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM commanders WHERE panel_user_id=?", (pu_id,)
        ).fetchone() is not None


def get_commander_zone_ids(pu_id: int) -> list:
    with get_conn() as conn:
        return [r["zone_id"] for r in conn.execute(
            "SELECT zone_id FROM commander_zones WHERE panel_user_id=?", (pu_id,)
        ).fetchall()]


def get_commander_permissions(pu_id: int) -> set:
    with get_conn() as conn:
        return {r["perm_key"] for r in conn.execute(
            "SELECT perm_key FROM commander_permissions WHERE panel_user_id=?", (pu_id,)
        ).fetchall()}


def commander_has_permission(pu_id: int, perm_key: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM commander_permissions WHERE panel_user_id=? AND perm_key=?",
            (pu_id, perm_key)
        ).fetchone() is not None


def commander_can_manage_zone(pu_id: int, zone_id: int) -> bool:
    """آیا این ناحیه تو لیستِ ناحیه‌های تحتِ فرماندهیِ این فرده؟"""
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM commander_zones WHERE panel_user_id=? AND zone_id=?",
            (pu_id, zone_id)
        ).fetchone() is not None


def get_all_commanders() -> list:
    """همه‌ی فرمانده‌ها، همراه با ناحیه‌ها و مجوزهاشون - برایِ صفحه‌ی
    مدیریتِ فرمانده‌ها تو پنلِ مالک."""
    with get_conn() as conn:
        pu_ids = [r["panel_user_id"] for r in conn.execute("SELECT panel_user_id FROM commanders").fetchall()]
    result = []
    for pid in pu_ids:
        with get_conn() as conn:
            pu = conn.execute("SELECT * FROM panel_users WHERE id=?", (pid,)).fetchone()
        if not pu:
            continue
        result.append({
            **dict(pu),
            "zone_ids": get_commander_zone_ids(pid),
            "permissions": sorted(get_commander_permissions(pid)),
            "user_creation_limit": get_commander_creation_limit(pid),
            "users_created_count": count_users_created_by(pid),
        })
    return result


def get_commander_managed_users(pu_id: int) -> list:
    """همه‌ی کاربرهایِ panel_users که تو ناحیه‌هایِ تحتِ فرماندهیِ این
    فرد هستن - مبنایِ لیستِ کاربرهایی که فرمانده می‌تونه رویشون کار کنه."""
    zone_ids = get_commander_zone_ids(pu_id)
    if not zone_ids:
        return []
    with get_conn() as conn:
        placeholders = ",".join("?" * len(zone_ids))
        rows = conn.execute(
            f"SELECT pu.*, z.name as zone_name FROM panel_users pu "
            f"JOIN zones z ON z.id = pu.zone_id "
            f"WHERE pu.zone_id IN ({placeholders}) ORDER BY z.name, pu.username",
            zone_ids
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# VIP Users
# ─────────────────────────────────────────────────────────────────────────────

def add_vip_user(user_id: int, username, first_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO vip_users (user_id, username, first_name) VALUES (?,?,?)",
            (user_id, username, first_name)
        )


def remove_vip_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM vip_users WHERE user_id=?", (user_id,))


def is_vip_user(user_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM vip_users WHERE user_id=?", (user_id,)
        ).fetchone() is not None


def get_all_vip_users() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT user_id, username, first_name, added_at FROM vip_users ORDER BY added_at"
        ).fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# Bot Admins
# ─────────────────────────────────────────────────────────────────────────────

def add_bot_admin(user_id: int, username, first_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_admins (user_id, username, first_name) VALUES (?,?,?)",
            (user_id, username, first_name)
        )


def remove_bot_admin(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM bot_admins WHERE user_id=?", (user_id,))


def is_bot_admin(user_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM bot_admins WHERE user_id=?", (user_id,)
        ).fetchone() is not None


def get_all_bot_admins() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM bot_admins").fetchall()]


def get_bot_admin(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM bot_admins WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Group Admins
# ─────────────────────────────────────────────────────────────────────────────

def add_group_admin(user_id: int, username, first_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO group_admins (user_id, username, first_name) VALUES (?,?,?)",
            (user_id, username, first_name)
        )


def remove_group_admin(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM group_admins WHERE user_id=?", (user_id,))


def is_group_admin(user_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM group_admins WHERE user_id=?", (user_id,)
        ).fetchone() is not None


def get_all_group_admins() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM group_admins").fetchall()]


def get_group_admin(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM group_admins WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Hashtags
# ─────────────────────────────────────────────────────────────────────────────

def add_hashtag(name: str, append_tag: bool = True, zone_id: int = None) -> int:
    """
    FIX #2: اگه هشتگ تکراری بود، id واقعی‌اش رو برمی‌گردونه نه None.
    zone_id: ناحیه‌ای که این هشتگ به آن تعلق دارد (برای فیلتر محتوا بر اساس
    ناحیه‌ی کاربر). برای محتوای بدون‌هشتگ/قدیمی می‌تواند None باشد.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO hashtags (name, append_tag, zone_id) VALUES (?,?,?)",
            (name, 1 if append_tag else 0, zone_id)
        )
        if cur.rowcount > 0 and cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM hashtags WHERE name=?", (name,)).fetchone()
        return row['id'] if row else None


def add_no_tag_group(name: str) -> int:
    """گروه بدون هشتگ — append_tag=0"""
    return add_hashtag(name, append_tag=False)


def get_no_tag_groups() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM hashtags WHERE append_tag=0 ORDER BY created_at DESC"
        ).fetchall()]


def get_all_hashtags() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM hashtags ORDER BY created_at DESC"
        ).fetchall()]


def get_active_hashtags() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM hashtags WHERE is_active=1 ORDER BY created_at DESC"
        ).fetchall()]


def set_hashtag_zones(hashtag_id: int, zone_ids: list):
    """جایگزینی کامل لیست ناحیه‌هایی که این هشتگ مخصوص اوناست. لیست خالی = برای همه."""
    with get_conn() as conn:
        conn.execute("DELETE FROM hashtag_zones WHERE hashtag_id=?", (hashtag_id,))
        for zid in set(zone_ids):
            conn.execute(
                "INSERT OR IGNORE INTO hashtag_zones (hashtag_id, zone_id) VALUES (?,?)",
                (hashtag_id, zid)
            )


def get_hashtag_zone_ids(hashtag_id: int) -> list:
    with get_conn() as conn:
        return [r['zone_id'] for r in conn.execute(
            "SELECT zone_id FROM hashtag_zones WHERE hashtag_id=?", (hashtag_id,)
        ).fetchall()]


def is_hashtag_visible_to_zone(hashtag_id: int, zone_id) -> bool:
    """آیا این هشتگ برای این ناحیه قابل‌مشاهده‌ست؟ zone_id=None یعنی ادمین/مالک (همیشه True)."""
    if zone_id is None:
        return True
    zids = get_hashtag_zone_ids(hashtag_id)
    if zids:
        return zone_id in zids
    ht = get_hashtag_by_id(hashtag_id)
    return bool(ht) and (ht.get('zone_id') is None or ht.get('zone_id') == zone_id)


def get_active_hashtags_for_zone(zone_id) -> list:
    """
    هشتگ‌های فعال قابل‌مشاهده برای یک ناحیه: هشتگ‌هایی که دقیقاً برای این
    ناحیه انتخاب شدن (از جدول hashtag_zones)، یا هشتگ‌هایی که هیچ ناحیه‌ی
    خاصی ندارن (یعنی «برای همه»). اگر zone_id=None باشد (ادمین/مالک)، همه‌ی
    هشتگ‌های فعال بدون فیلتر برگردانده می‌شود.
    """
    with get_conn() as conn:
        if zone_id is None:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM hashtags WHERE is_active=1 ORDER BY created_at DESC"
            ).fetchall()]
        return [dict(r) for r in conn.execute("""
            SELECT * FROM hashtags h WHERE h.is_active=1 AND (
                (NOT EXISTS (SELECT 1 FROM hashtag_zones hz WHERE hz.hashtag_id=h.id)
                 AND (h.zone_id IS NULL OR h.zone_id=?))
                OR EXISTS (SELECT 1 FROM hashtag_zones hz WHERE hz.hashtag_id=h.id AND hz.zone_id=?)
            )
            ORDER BY h.created_at DESC
        """, (zone_id, zone_id)).fetchall()]


def set_hashtag_active(hid: int, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE hashtags SET is_active=? WHERE id=?", (1 if active else 0, hid))


def deactivate_all_hashtags():
    with get_conn() as conn:
        conn.execute("UPDATE hashtags SET is_active=0")


def get_newest_hashtag():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hashtags ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_hashtag_by_id(hid: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM hashtags WHERE id=?", (hid,)).fetchone()
        return dict(row) if row else None


def delete_hashtag(hid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM hashtags WHERE id=?", (hid,))


def get_hashtag_stats() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT h.id, h.name,
                   COUNT(DISTINCT t.id) AS text_count,
                   COUNT(DISTINCT p.id) AS photo_count
            FROM hashtags h
            LEFT JOIN texts  t ON t.hashtag_id = h.id
            LEFT JOIN photos p ON p.hashtag_id = h.id
            GROUP BY h.id
            ORDER BY h.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Texts
# ─────────────────────────────────────────────────────────────────────────────

def add_texts(contents: list, hashtag_id: int) -> int:
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO texts (content, hashtag_id) VALUES (?,?)",
            [(c, hashtag_id) for c in contents]
        )
        return len(contents)


def count_texts() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) as c FROM texts").fetchone()['c']


def count_texts_by_hashtag(hid: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) as c FROM texts WHERE hashtag_id=?", (hid,)
        ).fetchone()['c']


def count_active_texts() -> int:
    active = get_active_hashtags()
    if not active:
        return 0
    ids = [h['id'] for h in active]
    ph  = ','.join('?' * len(ids))
    with get_conn() as conn:
        return conn.execute(
            f"SELECT COUNT(*) as c FROM texts WHERE hashtag_id IN ({ph})", ids
        ).fetchone()['c']


def pop_texts_with_ids(n: int, hashtag_id: int = None) -> list:
    with get_conn() as conn:
        if hashtag_id is not None:
            rows = conn.execute(
                "SELECT id, content FROM texts WHERE hashtag_id=? ORDER BY id ASC LIMIT ?",
                (hashtag_id, n)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content FROM texts ORDER BY id ASC LIMIT ?", (n,)
            ).fetchall()
        if not rows:
            return []
        ids = [r['id'] for r in rows]
        ph  = ','.join('?' * len(ids))
        conn.execute(f"DELETE FROM texts WHERE id IN ({ph})", ids)
        return [{'id': r['id'], 'content': r['content']} for r in rows]


def pop_texts(n: int) -> list:
    return [item['content'] for item in pop_texts_with_ids(n)]


def add_content_history(content_uid: int, kind: str, hashtag_id=None, media_type=None,
                         ref_id=None, text_content=None, caption=None, platform=None):
    """ثبت یه رکورد تاریخچه برای محتوایی که به کاربر داده شده - وب‌اپ (سایت
    و اپ، هر دو از همین یه Flask API استفاده می‌کنن) و بات، هرکدوم بعد از
    هر تحویل موفق این رو صدا می‌زنن. platform: 'app' | 'site' | 'bot'.
    برمی‌گردونه id ردیفِ تازه‌ساخته‌شده، برای اینکه فراخوان بتونه بعداً
    (وقتی کاربر دانلود/کپی کرد) دقیقاً همین ردیف رو آپدیت کنه."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO content_history
               (content_uid, kind, hashtag_id, media_type, ref_id, text_content, caption, platform)
               VALUES (?,?,?,?,?,?,?,?)""",
            (content_uid, kind, hashtag_id, media_type, ref_id, text_content, caption, platform),
        )
        return cur.lastrowid


def mark_content_downloaded(history_id: int, content_uid: int) -> bool:
    """کاربر دکمه‌ی «دانلود» رو زد. فقط اگه این ردیف واقعاً مالِ همین
    کاربر باشه آپدیت می‌شه (جلویِ این‌که یکی با حدسِ id، رکوردِ بقیه رو
    دستکاری کنه). فقط برایِ app/site معنی داره (بات امکانش رو نمی‌ده)."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE content_history SET downloaded_at=datetime('now') "
            "WHERE id=? AND content_uid=? AND downloaded_at IS NULL",
            (history_id, content_uid),
        )
        return cur.rowcount > 0


def mark_content_caption_copied(history_id: int, content_uid: int) -> bool:
    """کاربر کپشن/متن رو کپی کرد (همون منطقِ mark_content_downloaded)."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE content_history SET caption_copied_at=datetime('now') "
            "WHERE id=? AND content_uid=? AND caption_copied_at IS NULL",
            (history_id, content_uid),
        )
        return cur.rowcount > 0


def get_content_platform_stats(zone_id=None) -> dict:
    """آمارِ کلیِ پلتفرم + نشونه‌هایِ استفاده، اختیاری فقط برایِ یه ناحیه
    (با جوین به panel_users). خروجی: تعدادِ کل به تفکیکِ platform، و
    برایِ kindهایِ 'text'/'reel'/'story' (چیزهایی که دکمه‌ی دانلود/کپی
    دارن) چند درصدش downloaded/copied شده."""
    with get_conn() as conn:
        if zone_id is not None:
            base = ("FROM content_history ch JOIN panel_users pu ON pu.id = -ch.content_uid "
                    "WHERE pu.zone_id=?")
            params = (zone_id,)
        else:
            base = "FROM content_history ch"
            params = ()
        by_platform = {
            r["platform"] or "نامشخص": r["c"]
            for r in conn.execute(f"SELECT platform, COUNT(*) c {base} GROUP BY platform", params).fetchall()
        }
        usage_rows = conn.execute(
            f"""SELECT ch.kind,
                       COUNT(*) as total,
                       SUM(CASE WHEN ch.downloaded_at IS NOT NULL THEN 1 ELSE 0 END) as downloaded,
                       SUM(CASE WHEN ch.caption_copied_at IS NOT NULL THEN 1 ELSE 0 END) as copied
                {base} AND ch.kind IN ('text','reel','story')
                GROUP BY ch.kind""" if zone_id is not None else
            f"""SELECT ch.kind,
                       COUNT(*) as total,
                       SUM(CASE WHEN ch.downloaded_at IS NOT NULL THEN 1 ELSE 0 END) as downloaded,
                       SUM(CASE WHEN ch.caption_copied_at IS NOT NULL THEN 1 ELSE 0 END) as copied
                {base} WHERE ch.kind IN ('text','reel','story')
                GROUP BY ch.kind""",
            params,
        ).fetchall()
        by_kind = {r["kind"]: dict(r) for r in usage_rows}
        return {"by_platform": by_platform, "by_kind_usage": by_kind}


def get_content_platform_stats_per_user(zone_id=None) -> list:
    """مثلِ get_content_platform_stats ولی ردیف‌به‌ردیفِ هر کاربر - برایِ
    جدولِ «کاربرها» تویِ داشبورد."""
    with get_conn() as conn:
        if zone_id is not None:
            where = "WHERE pu.zone_id=?"
            params = (zone_id,)
        else:
            where = ""
            params = ()
        rows = conn.execute(
            f"""SELECT pu.id as panel_user_id, pu.username, pu.zone_id,
                       COUNT(ch.id) as total,
                       SUM(CASE WHEN ch.platform='app'  THEN 1 ELSE 0 END) as via_app,
                       SUM(CASE WHEN ch.platform='site' THEN 1 ELSE 0 END) as via_site,
                       SUM(CASE WHEN ch.platform='bot'  THEN 1 ELSE 0 END) as via_bot,
                       SUM(CASE WHEN ch.downloaded_at IS NOT NULL THEN 1 ELSE 0 END) as downloaded,
                       SUM(CASE WHEN ch.caption_copied_at IS NOT NULL THEN 1 ELSE 0 END) as copied
                FROM panel_users pu LEFT JOIN content_history ch ON ch.content_uid = -pu.id
                {where}
                GROUP BY pu.id
                ORDER BY total DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_content_history(content_uid: int, limit: int = 100) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ch.*, h.name as hashtag_name FROM content_history ch
               LEFT JOIN hashtags h ON h.id = ch.hashtag_id
               WHERE ch.content_uid=? ORDER BY ch.id DESC LIMIT ?""",
            (content_uid, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_texts_by_hashtag(hid: int):
    """حذف فقط متن‌های یک هشتگ (بدون حذف هشتگ)"""
    with get_conn() as conn:
        conn.execute("DELETE FROM texts WHERE hashtag_id=?", (hid,))


# ─────────────────────────────────────────────────────────────────────────────
# Photos
# ─────────────────────────────────────────────────────────────────────────────

def add_photo(file_id: str, hashtag_id: int, media_type: str = 'photo'):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO photos (file_id, hashtag_id, media_type) VALUES (?,?,?)",
            (file_id, hashtag_id, media_type)
        )


def count_photos_by_hashtag(hid: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) as c FROM photos WHERE hashtag_id=?", (hid,)
        ).fetchone()['c']


def get_photo_by_hashtag(hashtag_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE hashtag_id=? ORDER BY RANDOM() LIMIT 1",
            (hashtag_id,)
        ).fetchone()
        return dict(row) if row else None


def get_unreceived_photos_batch(user_id: int, hashtag_id: int, limit: int = 10) -> list:
    """
    برخلاف get_next_sequential_photo (که فقط یک عکس برمی‌گرداند)، این تابع تا
    `limit` عکسی که کاربر هنوز دریافت نکرده را یک‌جا برمی‌گرداند — برای ارسال
    دسته‌ای/همزمان به‌جای یکی‌یکی.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.* FROM photos p
            WHERE p.hashtag_id = ?
              AND p.id NOT IN (
                  SELECT photo_id FROM user_received_photos WHERE user_id = ?
              )
            ORDER BY p.id ASC LIMIT ?
            """,
            (hashtag_id, user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_next_sequential_photo(user_id: int, hashtag_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.* FROM photos p
            WHERE p.hashtag_id = ?
              AND p.id NOT IN (
                  SELECT photo_id FROM user_received_photos WHERE user_id = ?
              )
            ORDER BY p.id ASC LIMIT 1
            """,
            (hashtag_id, user_id)
        ).fetchone()
        return dict(row) if row else None


def fix_photo_media_type(photo_id: int, correct_type: str):
    """
    وقتی تلگرام واقعاً بگه فایل از نوع دیگه‌ایه (مثلاً یه ویدیوی قدیمی که با
    media_type='photo' ثبت شده بود، قبل از اینکه این ستون اضافه بشه)، این
    تابع نوع درست رو توی دیتابیس اصلاح می‌کنه تا دفعه‌ی بعد درست فرستاده شه.
    """
    with get_conn() as conn:
        conn.execute("UPDATE photos SET media_type=? WHERE id=?", (correct_type, photo_id))


def fix_story_media_type(story_id: int, correct_type: str):
    with get_conn() as conn:
        conn.execute("UPDATE stories SET media_type=? WHERE id=?", (correct_type, story_id))


def mark_photo_received(user_id: int, photo_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_received_photos (user_id, photo_id) VALUES (?,?)",
            (user_id, photo_id)
        )


def reset_user_photos_for_hashtag(user_id: int, hashtag_id: int):
    with get_conn() as conn:
        conn.execute(
            """
            DELETE FROM user_received_photos
            WHERE user_id = ?
              AND photo_id IN (SELECT id FROM photos WHERE hashtag_id = ?)
            """,
            (user_id, hashtag_id)
        )


def delete_photos_by_hashtag(hid: int):
    """حذف فقط عکس‌های یک هشتگ (بدون حذف هشتگ)"""
    with get_conn() as conn:
        conn.execute("DELETE FROM photos WHERE hashtag_id=?", (hid,))


# ─────────────────────────────────────────────────────────────────────────────
# Instagram — Reels
# برخلاف متن/عکس، ریلز هرگز از مخزن حذف نمی‌شود؛ فقط برای هر کاربر یک‌بار
# «مصرف» می‌شود (رکورد در user_received_reels). وقتی کاربر همه‌ی ریلزهای یک
# هشتگ را گرفت، get_unreceived_reel چیزی برنمی‌گرداند (None) — نه به این معنی
# که مخزن خالی است، بلکه یعنی چیز جدیدی برای همین کاربر نمانده.
# ─────────────────────────────────────────────────────────────────────────────

def add_reel(file_id: str, caption: str, hashtag_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reels (file_id, caption, hashtag_id) VALUES (?,?,?)",
            (file_id, caption, hashtag_id)
        )


def count_reels_by_hashtag(hid: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) as c FROM reels WHERE hashtag_id=?", (hid,)
        ).fetchone()['c']


def delete_reels_by_hashtag(hid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM reels WHERE hashtag_id=?", (hid,))


def get_unreceived_reel(user_id: int, hashtag_id: int):
    """یک ریلز که این کاربر هنوز نگرفته را برمی‌گرداند، یا None اگر همه را گرفته."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT r.* FROM reels r
            WHERE r.hashtag_id = ?
              AND r.id NOT IN (
                  SELECT reel_id FROM user_received_reels WHERE user_id = ?
              )
            ORDER BY r.id ASC LIMIT 1
            """,
            (hashtag_id, user_id)
        ).fetchone()
        return dict(row) if row else None


def mark_reel_received(user_id: int, reel_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_received_reels (user_id, reel_id) VALUES (?,?)",
            (user_id, reel_id)
        )


def has_unreceived_reel(user_id: int, hashtag_id: int) -> bool:
    return get_unreceived_reel(user_id, hashtag_id) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Instagram — Stories (مثل ریلز، فقط بدون کپشن)
# ─────────────────────────────────────────────────────────────────────────────

def add_story(file_id: str, hashtag_id: int, media_type: str = 'photo'):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO stories (file_id, hashtag_id, media_type) VALUES (?,?,?)",
            (file_id, hashtag_id, media_type)
        )


def count_stories_by_hashtag(hid: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) as c FROM stories WHERE hashtag_id=?", (hid,)
        ).fetchone()['c']


def delete_stories_by_hashtag(hid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM stories WHERE hashtag_id=?", (hid,))


def get_unreceived_story(user_id: int, hashtag_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT s.* FROM stories s
            WHERE s.hashtag_id = ?
              AND s.id NOT IN (
                  SELECT story_id FROM user_received_stories WHERE user_id = ?
              )
            ORDER BY s.id ASC LIMIT 1
            """,
            (hashtag_id, user_id)
        ).fetchone()
        return dict(row) if row else None


def mark_story_received(user_id: int, story_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_received_stories (user_id, story_id) VALUES (?,?)",
            (user_id, story_id)
        )


def has_unreceived_story(user_id: int, hashtag_id: int) -> bool:
    return get_unreceived_story(user_id, hashtag_id) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Instagram — محدودیت‌ها (تعداد + ساعت، جدا برای ریلز و استوری)
# ─────────────────────────────────────────────────────────────────────────────

def get_reel_limit(zone_id=None) -> int:
    try: return int(get_zone_setting(zone_id, 'reel_limit', 3))
    except (ValueError, TypeError): return 3

def set_reel_limit(n: int, zone_id=None): set_zone_setting(zone_id, 'reel_limit', str(n))

def get_reel_cooldown_hours(zone_id=None) -> int:
    try: return int(get_zone_setting(zone_id, 'reel_cooldown_hours', 1))
    except (ValueError, TypeError): return 1

def set_reel_cooldown_hours(h: int, zone_id=None): set_zone_setting(zone_id, 'reel_cooldown_hours', str(h))

def get_story_limit(zone_id=None) -> int:
    try: return int(get_zone_setting(zone_id, 'story_limit', 3))
    except (ValueError, TypeError): return 3

def set_story_limit(n: int, zone_id=None): set_zone_setting(zone_id, 'story_limit', str(n))

def get_story_cooldown_hours(zone_id=None) -> int:
    try: return int(get_zone_setting(zone_id, 'story_cooldown_hours', 1))
    except (ValueError, TypeError): return 1

def set_story_cooldown_hours(h: int, zone_id=None): set_zone_setting(zone_id, 'story_cooldown_hours', str(h))


def check_content_cooldown(user_id: int, content_type: str, allowance: int, cooldown_h: int) -> tuple:
    """
    نسخه‌ی عمومی‌شده‌ی check_cooldown (که برای متن توییتر استفاده می‌شود) برای
    محتوای اینستاگرام. content_type: 'reel' یا 'story'.
    خروجی: (remaining, locked_until | None)
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT sent_count, locked_until FROM user_content_cooldown WHERE user_id=? AND content_type=?",
            (user_id, content_type)
        ).fetchone()
        if not row:
            return allowance, None

        if row['locked_until']:
            locked_until = datetime.fromisoformat(row['locked_until'])
            if datetime.utcnow() < locked_until:
                sent = row['sent_count']
                if sent < allowance:
                    conn.execute(
                        "UPDATE user_content_cooldown SET locked_until=NULL WHERE user_id=? AND content_type=?",
                        (user_id, content_type)
                    )
                    return allowance - sent, None
                return 0, locked_until
            conn.execute(
                "UPDATE user_content_cooldown SET sent_count=0, locked_until=NULL, notified=0 "
                "WHERE user_id=? AND content_type=?",
                (user_id, content_type)
            )
            return allowance, None

        remaining = max(0, allowance - row['sent_count'])
        if remaining == 0:
            locked_until = (datetime.utcnow() + timedelta(hours=cooldown_h)).isoformat()
            conn.execute(
                "UPDATE user_content_cooldown SET locked_until=?, notified=0 WHERE user_id=? AND content_type=?",
                (locked_until, user_id, content_type)
            )
            return 0, datetime.fromisoformat(locked_until)
        return remaining, None


def update_content_cooldown(user_id: int, content_type: str, add_count: int, cooldown_h: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT sent_count, locked_until FROM user_content_cooldown WHERE user_id=? AND content_type=?",
            (user_id, content_type)
        ).fetchone()
        now = datetime.utcnow()

        if row and row['locked_until']:
            lu = datetime.fromisoformat(row['locked_until'])
            if now < lu:
                return
            conn.execute(
                "UPDATE user_content_cooldown SET sent_count=0, locked_until=NULL, notified=0 "
                "WHERE user_id=? AND content_type=?",
                (user_id, content_type)
            )
            row = None

        if row:
            new_count = row['sent_count'] + add_count
            conn.execute(
                "UPDATE user_content_cooldown SET sent_count=? WHERE user_id=? AND content_type=?",
                (new_count, user_id, content_type)
            )
        else:
            conn.execute(
                "INSERT INTO user_content_cooldown (user_id, content_type, sent_count) VALUES (?,?,?)",
                (user_id, content_type, add_count)
            )


# ─────────────────────────────────────────────────────────────────────────────
# Instagram VIP (کاملاً جدا از VIP توییتر)
# ─────────────────────────────────────────────────────────────────────────────

def add_instagram_vip_user(user_id: int, username, first_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO instagram_vip_users (user_id, username, first_name) VALUES (?,?,?)",
            (user_id, username, first_name)
        )

def remove_instagram_vip_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM instagram_vip_users WHERE user_id=?", (user_id,))

def is_instagram_vip_user(user_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM instagram_vip_users WHERE user_id=?", (user_id,)
        ).fetchone() is not None

def get_all_instagram_vip_users() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM instagram_vip_users").fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# آنتی‌فلود
# ─────────────────────────────────────────────────────────────────────────────

def get_flood_state(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM user_flood WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def flood_temp_block(user_id: int, minutes: int = 30):
    until = (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_flood (user_id, offense_count, blocked_until) VALUES (?, 1, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "offense_count = offense_count + 1, blocked_until = ?",
            (user_id, until, until)
        )


def flood_permanent_block(user_id: int, notice_chat_id: int, notice_msg_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_flood (user_id, offense_count, permanently_blocked, notice_chat_id, notice_msg_id) "
            "VALUES (?, 1, 1, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "permanently_blocked = 1, notice_chat_id = ?, notice_msg_id = ?",
            (user_id, notice_chat_id, notice_msg_id, notice_chat_id, notice_msg_id)
        )


def flood_clear_temp_block(user_id: int):
    """پس از سپری شدن ۳۰ دقیقه، فقط قفل موقت برداشته می‌شود؛ offense_count دست‌نخورده می‌ماند
    تا اگر دوباره تخلف کرد، به‌عنوان تخلف دوم (مسدودی دائم) شناسایی شود."""
    with get_conn() as conn:
        conn.execute("UPDATE user_flood SET blocked_until=NULL WHERE user_id=?", (user_id,))


def flood_forgive_permanent(user_id: int):
    """وقتی owner دکمه‌ی «رحمش کن» را می‌زند: کاربر کاملاً از صفر شروع می‌کند."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_flood SET permanently_blocked=0, offense_count=0, "
            "blocked_until=NULL, notice_chat_id=NULL, notice_msg_id=NULL WHERE user_id=?",
            (user_id,)
        )


def get_expired_temp_blocks() -> list:
    """کاربرانی که مسدودی موقت‌شان تمام شده ولی هنوز پیام «بخشیدمت» نگرفته‌اند."""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id FROM user_flood "
            "WHERE blocked_until IS NOT NULL AND blocked_until <= ? AND permanently_blocked=0",
            (now,)
        ).fetchall()
        return [r['user_id'] for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# Transfer content
# ─────────────────────────────────────────────────────────────────────────────

def transfer_content(src_hid: int, dst_hid: int, content_type: str, cut: bool = False) -> int:
    """
    کپی یا انتقال محتوا بین دو هشتگ.
    content_type: 'text' | 'photo' | 'all' (توییتر) | 'reel' | 'story' | 'all_ig' (اینستاگرام)
    cut=True → برداشتن (حذف از مبدأ)
    برمی‌گردونه تعداد موارد منتقل‌شده.
    """
    moved = 0
    with get_conn() as conn:
        if content_type in ('text', 'all'):
            texts = conn.execute(
                "SELECT id, content FROM texts WHERE hashtag_id=?", (src_hid,)
            ).fetchall()
            if texts:
                conn.executemany(
                    "INSERT INTO texts (content, hashtag_id) VALUES (?,?)",
                    [(r['content'], dst_hid) for r in texts]
                )
                moved += len(texts)
                if cut:
                    ids = [r['id'] for r in texts]
                    ph  = ','.join('?' * len(ids))
                    conn.execute(f"DELETE FROM texts WHERE id IN ({ph})", ids)

        if content_type in ('photo', 'all'):
            photos = conn.execute(
                "SELECT id, file_id FROM photos WHERE hashtag_id=?", (src_hid,)
            ).fetchall()
            if photos:
                conn.executemany(
                    "INSERT INTO photos (file_id, hashtag_id) VALUES (?,?)",
                    [(r['file_id'], dst_hid) for r in photos]
                )
                moved += len(photos)
                if cut:
                    ids = [r['id'] for r in photos]
                    ph  = ','.join('?' * len(ids))
                    conn.execute(f"DELETE FROM photos WHERE id IN ({ph})", ids)

        if content_type in ('reel', 'all_ig'):
            reels = conn.execute(
                "SELECT id, file_id, caption FROM reels WHERE hashtag_id=?", (src_hid,)
            ).fetchall()
            if reels:
                conn.executemany(
                    "INSERT INTO reels (file_id, caption, hashtag_id) VALUES (?,?,?)",
                    [(r['file_id'], r['caption'], dst_hid) for r in reels]
                )
                moved += len(reels)
                if cut:
                    ids = [r['id'] for r in reels]
                    ph  = ','.join('?' * len(ids))
                    conn.execute(f"DELETE FROM reels WHERE id IN ({ph})", ids)

        if content_type in ('story', 'all_ig'):
            stories = conn.execute(
                "SELECT id, file_id FROM stories WHERE hashtag_id=?", (src_hid,)
            ).fetchall()
            if stories:
                conn.executemany(
                    "INSERT INTO stories (file_id, hashtag_id) VALUES (?,?)",
                    [(r['file_id'], dst_hid) for r in stories]
                )
                moved += len(stories)
                if cut:
                    ids = [r['id'] for r in stories]
                    ph  = ','.join('?' * len(ids))
                    conn.execute(f"DELETE FROM stories WHERE id IN ({ph})", ids)

    return moved


# ─────────────────────────────────────────────────────────────────────────────
# Groups (bot membership)
# ─────────────────────────────────────────────────────────────────────────────

def add_group(group_id: int, group_name: str, group_link: str = 'N/A'):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_groups (group_id, group_name, group_link) VALUES (?,?,?)",
            (group_id, group_name, group_link)
        )


def remove_group(group_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM bot_groups WHERE group_id=?", (group_id,))


def get_all_groups() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM bot_groups ORDER BY joined_at"
        ).fetchall()]


def update_group_link(group_id: int, link: str):
    with get_conn() as conn:
        conn.execute("UPDATE bot_groups SET group_link=? WHERE group_id=?", (link, group_id))


