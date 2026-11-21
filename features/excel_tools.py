"""ابزارِ کمکیِ خوندنِ فایلِ اکسلِ یوزرنیم/پسورد برایِ ایمپورتِ دسته‌ای
کاربر از طریقِ بات (فازِ ۴ از نقشه‌راهِ پنلِ مدیریتی). اکسپورت (فازِ ۵)
هم بعداً همینجا اضافه می‌شه تا هر دو طرفِ کار (خوندن/نوشتن) یه‌جا باشن.
"""
import io

from openpyxl import load_workbook

# سقفِ حجمِ فایلِ ورودی - بات هم محدودیتِ دانلودِ ۲۰ مگابایتی داره، ولی
# یه فایلِ اکسلِ چندهزارردیفی هم عملاً همین‌قدر کافیه؛ سقفِ کوچیک‌تر
# یعنی خطاهایِ واضح‌تر برایِ فایل‌هایِ اشتباهی (مثلاً عکس با پسوندِ عوضی).
MAX_XLSX_SIZE_BYTES = 5 * 1024 * 1024  # ۵ مگابایت

_HEADER_HINTS = {'username', 'user', 'یوزرنیم', 'نام کاربری'}
_PASSWORD_HEADER_HINTS = {'password', 'pass', 'پسورد', 'پسوورد', 'رمز', 'رمز عبور', 'رمزعبور'}


class XlsxParseError(Exception):
    """خطایِ قابل‌نمایش‌به‌کاربر (نه یه ترسِ داخلی) - پیامش مستقیم قابلِ
    فرستادن به چتِ تلگرامه."""


def parse_users_xlsx(file_bytes: bytes) -> list[tuple[str, str]]:
    """فازِ ادامه: فقط ستونِ «یوزرنیم» و «پسورد/پسوورد» رو از رویِ متنِ
    هدرِ ردیفِ اول پیدا می‌کنه و می‌خونه - بدونِ توجه به اینکه چندتا
    ستونِ دیگه (شماره، اسمِ نمایشی، ...) قبل/بین/بعدشون باشه یا نه.
    اگه هدر پیدا نشد (مثلاً فایل اصلاً هدر نداره)، برمی‌گرده به رفتارِ
    قدیمی: ستونِ اول یوزرنیم، ستونِ دوم پسورد.
    ردیف‌هایی که یوزرنیمشون خالیه رد می‌شن (نه خطا - شاید فقط یه
    ردیفِ خالیِ میونیِ اکسل باشه)."""
    if len(file_bytes) > MAX_XLSX_SIZE_BYTES:
        raise XlsxParseError(
            f'فایل خیلی بزرگه (بیشتر از {MAX_XLSX_SIZE_BYTES // 1024 // 1024} مگابایت). '
            'یه فایلِ کوچیک‌تر بفرست.'
        )
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        raise XlsxParseError('این فایل یه اکسلِ معتبر (.xlsx) نیست یا خرابه.')

    if not rows:
        raise XlsxParseError('فایل خالیه.')

    # ۱) دنبالِ ستونِ یوزرنیم/پسورد از رویِ متنِ هدرِ ردیفِ اول بگرد
    header = rows[0] or ()
    uname_col = pw_col = None
    for idx, cell in enumerate(header):
        if cell is None:
            continue
        text = str(cell).strip().lower()
        if uname_col is None and text in _HEADER_HINTS:
            uname_col = idx
        elif pw_col is None and text in _PASSWORD_HEADER_HINTS:
            pw_col = idx
    has_header = uname_col is not None and pw_col is not None

    # ۲) اگه هدرِ قابل‌شناسایی نبود، برگرد به حالتِ قدیمی: ستونِ ۱ و ۲
    if not has_header:
        uname_col, pw_col = 0, 1

    pairs: list[tuple[str, str]] = []
    start_row = 1 if has_header else 0
    for i, row in enumerate(rows[start_row:], start=start_row):
        if not row or len(row) <= uname_col:
            continue
        raw_uname = row[uname_col]
        raw_pw = row[pw_col] if pw_col < len(row) else None
        if raw_uname is None:
            continue
        uname = str(raw_uname).strip()
        pw = '' if raw_pw is None else str(raw_pw).strip()
        if not uname:
            continue
        if not has_header and i == 0 and uname.lower() in _HEADER_HINTS:
            continue  # حالتِ قدیمی: ردیفِ هدر بودنش رو از رویِ خودِ متن حدس بزن
        pairs.append((uname, pw))

    if not pairs:
        raise XlsxParseError(
            'هیچ ردیفِ قابل‌استفاده‌ای تو فایل پیدا نشد. یه ستون با هدرِ '
            '«یوزرنیم» و یه ستون با هدرِ «پسورد» داشته باش (یا اگه هدر '
            'نمی‌ذاری، ستونِ اول یوزرنیم و ستونِ دوم پسورد باشه).'
        )
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# ایمپورتِ کاملِ کاربر (اسم کاربر | یوزرنیم | پسوورد | شماره تلفن | کد ملی)
# ─────────────────────────────────────────────────────────────────────────────
def _norm_header(v) -> str:
    """متنِ هدر رو برایِ مقایسه یکدست می‌کنه: حروفِ عربی→فارسی، حذفِ نیم‌فاصله/فاصله/
    علامت‌ها، lowercase."""
    t = str(v or "").strip().lower()
    t = t.replace("ي", "ی").replace("ك", "ک").replace("\u200c", "").replace("\u200f", "")
    for ch in (" ", "_", "-", ".", ":", "ـ", "(", ")"):
        t = t.replace(ch, "")
    return t


_COL_HINTS = {
    "real_name": {"اسمکاربر", "اسم", "نام", "نامونامخانوادگی", "نامنامخانوادگی", "نامکامل", "اسمواقعی",
                  "نامواقعی", "نامخانوادگی", "name", "fullname", "realname"},
    "username": {"یوزرنیم", "نامکاربری", "یوزر", "username", "user", "login"},
    "password": {"پسوورد", "پسورد", "رمز", "رمزعبور", "رمزورود", "password", "pass", "pwd"},
    "phone": {"شمارهتلفن", "شمارهتفلن", "شمارهتماس", "تلفن", "تفلن", "موبایل", "همراه", "شماره",
              "شمارهموبایل", "شمارههمراه", "phone", "mobile", "tel"},
    "national_id": {"کدملی", "کدملیکاربر", "شمارهملی", "کدشناسایی", "nationalid", "nid", "melli", "کدملی۱۰رقمی"},
}


def _cell_text(v) -> str:
    """مقدارِ سلول → متن. عددهایِ اکسل (int/float) بدونِ «.0»؛ صفرِ اولِ افتاده
    رو خودِ نرمال‌سازِ شماره/کدِ ملی برمی‌گردونه."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def parse_users_full(file_bytes: bytes) -> list[dict]:
    """فایلِ اکسلِ ایمپورتِ کاربرها → لیستِ dict با کلیدهایِ
    row, real_name, username, password, phone, national_id (همه str، ممکنه خالی باشن).
    ستون‌ها از رویِ متنِ هدرِ ردیفِ اول شناخته می‌شن (ترتیب مهم نیست؛ ستونِ
    «ردیف/شماره‌گذاری» نادیده گرفته می‌شه). اگه هدرِ قابل‌شناسایی نبود → حالتِ قدیمی:
    ستونِ ۱ یوزرنیم، ستونِ ۲ پسورد. ردیف‌هایِ کاملاً خالی رد می‌شن."""
    if len(file_bytes) > MAX_XLSX_SIZE_BYTES:
        raise XlsxParseError(
            f"فایل خیلی بزرگه (بیشتر از {MAX_XLSX_SIZE_BYTES // 1024 // 1024} مگابایت). یه فایلِ کوچیک‌تر بفرست."
        )
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        raise XlsxParseError("این فایل یه اکسلِ معتبر (.xlsx) نیست یا خرابه.")
    if not rows:
        raise XlsxParseError("فایل خالیه.")

    # هدر: اولین ردیفی (از ۵ ردیفِ اول) که حداقل یکی از ستون‌هایِ شناخته‌شده رو داشته باشه
    col_of: dict[str, int] = {}
    header_idx = None
    for ri, row in enumerate(rows[:5]):
        found: dict[str, int] = {}
        for ci, cell in enumerate(row or ()):
            if cell is None:
                continue
            h = _norm_header(cell)
            for key, hints in _COL_HINTS.items():
                if key not in found and h in hints:
                    found[key] = ci
                    break
        if found and ("username" in found or "real_name" in found):
            col_of, header_idx = found, ri
            break

    if header_idx is None:
        col_of, header_idx = {"username": 0, "password": 1}, -1
        if rows and _norm_header((rows[0] or (None,))[0]) in _COL_HINTS["username"]:
            header_idx = 0

    out: list[dict] = []
    for ri in range(header_idx + 1, len(rows)):
        row = rows[ri] or ()
        item = {"row": ri + 1}
        for key in ("real_name", "username", "password", "phone", "national_id"):
            ci = col_of.get(key)
            item[key] = _cell_text(row[ci]) if ci is not None and ci < len(row) else ""
        if not any(item[k] for k in ("real_name", "username", "password", "phone", "national_id")):
            continue
        out.append(item)

    if not out:
        raise XlsxParseError(
            "هیچ ردیفِ قابل‌استفاده‌ای تو فایل پیدا نشد. هدرِ ستون‌ها باید این‌ها باشه: "
            "اسم کاربر، یوزرنیم، پسوورد، شماره تلفن، کد ملی."
        )
    return out


def build_import_template() -> bytes:
    """قالبِ خالیِ ایمپورت (همون چیدمانِ فایلی که مالک استفاده می‌کنه): ستونِ A
    شماره‌ی ردیف، بعد اسم کاربر | یوزرنیم | پسوورد | شماره تلفن | کد ملی. ستون‌هایِ
    شماره/کدِ ملی «متن» هستن تا اکسل صفرِ اول رو نخوره."""
    wb = Workbook()
    ws = wb.active
    ws.title = "کاربرها"
    ws.sheet_view.rightToLeft = True
    ws.append([None, "اسم کاربر", "یوزرنیم", "پسوورد", "شماره تلفن", "کد ملی"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for i in range(1, 31):
        ws.append([i])
    for r in range(2, 32):
        for c in (5, 6):
            ws.cell(row=r, column=c).number_format = "@"
    for col, w in zip("ABCDEF", (6, 26, 18, 18, 16, 14)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# اکسپورت (فازِ ۵) - ساختِ فایلِ اکسل از رویِ دیتایِ آماده‌شده تو database.py
# ─────────────────────────────────────────────────────────────────────────────
from openpyxl import Workbook
from openpyxl.styles import Font


def _autosize_columns(ws):
    """پهنایِ هر ستون رو بر اساسِ طولِ محتوا تنظیم می‌کنه - وگرنه ستون‌ها
    پیش‌فرضِ اکسل (خیلی باریک) می‌مونن و باز کردنِ فایل همیشه با
    ریسایزِ دستی همراه می‌شه."""
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(length + 2, 10), 40)


def build_new_users_xlsx(users: list, zone_name: str) -> bytes:
    """فازِ ۸ - خروجیِ سبکِ فقط یوزرنیم/پسورد برایِ همون دسته‌ای که تازه
    ساخته شده (خروجیِ database.bulk_create_panel_users)؛ برخلافِ
    build_users_xlsx نیازی به ردیف‌هایِ کاملِ get_export_rows نداره،
    چون این کاربرهایِ تازه‌ساخته‌شده هنوز نه VIPـن نه سرپرست نه چیزِ
    دیگه‌ای - همون یوزرنیم/پسورد کافیه."""
    wb = Workbook()
    ws = wb.active
    ws.title = "کاربرهای تازه"
    ws.append(["یوزرنیم", "پسورد", "ناحیه"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for u in users:
        ws.append([u["username"], u["password"], zone_name])
    _autosize_columns(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_users_xlsx(rows: list, include_password: bool = True, include_identity: bool = False,
                     include_real_name: bool = False) -> bytes:
    """rows: خروجیِ database.get_export_rows(). include_password=False
    برایِ وقتی درخواست‌کننده مجوزِ دیدنِ پسورد نداره - ستونِ پسورد اصلاً
    تویِ فایل نمی‌آد (نه اینکه خالی باشه، چون یه ستونِ خالی خودش یعنی
    "پسورد نداره" که گمراه‌کننده‌ست).
    include_identity=True (فقط مالک): اسمِ واقعی / شماره تلفن / کدِ ملی هم
    (از رویِ users_hub.attach_identity) اضافه می‌شن؛ شماره و کدِ ملی به‌صورتِ
    متن نوشته می‌شن تا صفرِ اول نیفته."""
    wb = Workbook()
    ws = wb.active
    ws.title = "کاربرها"
    headers = ["یوزرنیم"]
    if include_password:
        headers.append("پسورد")
    if include_identity:
        headers += ["اسم کاربر", "شماره تلفن", "کد ملی"]
    elif include_real_name:  # فرمانده‌ایی که فقط مجوزِ دیدنِ اسمِ واقعی دارن
        headers += ["اسم کاربر"]
    headers += ["ناحیه", "اسمِ نمایشی", "وارد شده به بات؟", "VIP توییتر", "VIP اینستاگرام", "سرپرست؟", "فرمانده؟", "تاریخِ عضویت"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r in rows:
        row = [r["username"]]
        if include_password:
            row.append(r.get("password") or "")
        if include_identity:
            row += [r.get("real_name") or "", r.get("phone") or "", r.get("national_id") or ""]
        elif include_real_name:
            row += [r.get("real_name") or ""]
        row += [
            r["zone_name"], r["display_name"],
            "بله" if r["telegram_linked"] else "خیر",
            "بله" if r["is_vip_twitter"] else "خیر",
            "بله" if r["is_vip_instagram"] else "خیر",
            "بله" if r["is_supervisor"] else "خیر",
            "بله" if r["is_commander"] else "خیر",
            r["created_at"],
        ]
        ws.append(row)
        if include_identity:
            base = 3 if include_password else 2  # شمارهٔ ستونِ (۰-پایه) اولین ستونِ هویتی
            for off in (1, 2):  # تلفن، کدِ ملی
                ws.cell(row=ws.max_row, column=base + off + 1).number_format = "@"
    _autosize_columns(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_zones_xlsx(rows: list) -> bytes:
    """rows: خروجیِ database.get_zones_export_rows()."""
    wb = Workbook()
    ws = wb.active
    ws.title = "ناحیه‌ها"
    ws.append(["اسمِ ناحیه", "تعدادِ کاربر", "فرمانده(ها)", "تاریخِ ساخت"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r in rows:
        ws.append([r["name"], r["user_count"], r["commander_usernames"], r["created_at"]])
    _autosize_columns(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_stats_xlsx(ov: dict) -> bytes:
    """فازِ ۵۸ - خروجیِ اکسلِ آمارِ پیشرفته (خروجیِ app_features.overview).
    چهار شیت: خلاصه، روزانه، ناحیه‌ها، ساعت‌ها/پرطرفدارها."""
    wb = Workbook()

    def sheet(ws, header, rows):
        ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for r in rows:
            ws.append(r)
        _autosize_columns(ws)

    ws = wb.active
    ws.title = "خلاصه"
    k = ov.get("kinds", {})
    a = ov.get("active", {})
    sheet(ws, ["شاخص", "مقدار"], [
        ["بازه (روز)", ov.get("days")],
        ["کلِ کاربرها", ov.get("users_total")],
        ["فعالِ امروز", a.get("today")],
        ["فعالِ ۷ روز", a.get("d7")],
        ["فعالِ ۳۰ روز", a.get("d30")],
        ["ورود", k.get("login", 0)],
        ["بازکردنِ اپ", k.get("open", 0)],
        ["دریافتِ محتوا", k.get("content", 0)],
        ["پیام", k.get("message", 0)],
    ])
    sheet(wb.create_sheet("روزانه"), ["تاریخ", "کاربرِ فعال", "رویداد", "کاربرِ جدید", "کلِ کاربرها"],
          [[d["date"], d["active"], d["events"], d["new_users"], d["users_total"]] for d in ov.get("daily", [])])
    sheet(wb.create_sheet("ناحیه‌ها"), ["ناحیه", "کاربرِ فعال", "رویداد"],
          [[z["name"], z["users"], z["events"]] for z in ov.get("zones", [])])
    ws4 = wb.create_sheet("ساعت و محتوا")
    rows = [[f"{h:02d}:00", c] for h, c in enumerate(ov.get("hours", []))]
    rows.append([])
    rows.append(["هشتگ", "تعدادِ دریافت", "کاربر"])
    rows += [[t["name"], t["count"], t["users"]] for t in ov.get("top_content", [])]
    fl = (ov.get("follows") or {}).get("top") or []
    if fl:  # فازِ ۶۱
        rows.append([])
        rows.append(["پردنبال‌ترین هشتگ‌ها", "دنبال‌کننده"])
        rows += [[t["name"], t["followers"]] for t in fl]
    sheet(ws4, ["ساعت (تهران)", "رویداد"], rows)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_poll_xlsx(d: dict) -> bytes:
    """فازِ ۶۰ - خروجیِ اکسلِ نتیجه‌یِ یک نظرسنجی (خروجیِ polls.owner_detail).
    رأی‌دهنده‌ها فقط برایِ نظرسنجیِ غیرناشناس هست."""
    wb = Workbook()
    ws = wb.active
    ws.title = "نتیجه"
    ws.append(["سؤال", d["question"]])
    ws.append(["مخاطب", d["audience_label"]])
    ws.append(["نوع", ("چندگزینه‌ای" if d["multi"] else "تک‌گزینه‌ای") + " · " + ("ناشناس" if d["anonymous"] else "با نامِ رأی‌دهنده")])
    ws.append(["تعدادِ رأی‌دهنده", d["total"]])
    ws.append([])
    ws.append(["گزینه", "تعدادِ رأی", "درصد"])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    for o in d["options"]:
        ws.append([o["text"], o["count"], o["pct"]])
    _autosize_columns(ws)
    if not d["anonymous"]:
        ws2 = wb.create_sheet("رأی‌دهنده‌ها")
        ws2.append(["گزینه", "رأی‌دهنده"])
        for cell in ws2[1]:
            cell.font = Font(bold=True)
        for o in d["options"]:
            for n in o.get("voters", []):
                ws2.append([o["text"], n])
        _autosize_columns(ws2)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
