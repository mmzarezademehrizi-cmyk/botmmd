# -*- coding: utf-8 -*-
"""نسخه‌یِ مستقل: ذخیره‌یِ دائمیِ عکس/ویدیو برایِ سایت لازم نیست؛ فایل‌ها همون‌جا توی خودِ تلگرام می‌مونن."""


def cache_async(file_id, media_type="photo"):
    return None


def probe_async(file_id, media_type="photo"):
    return None


def is_unavailable(file_id, media_type="photo"):
    return False


def unavailable_ids(file_ids):
    return set()
