# -*- coding: utf-8 -*-
"""نسخه‌یِ مستقل: پوشِ اپ (Firebase) وجود نداره؛ همه‌یِ توابع بی‌اثرن تا کدِ ربات بدونِ تغییر کار کنه."""


def is_configured() -> bool:
    return False


def _send_to_tokens(tokens, title, body):
    return None


def notify(notif_key, recipients, **template_vars):
    return None


def notify_zone(notif_key, zone_id, _user_filter=None, **template_vars):
    return None


def notify_content_available(kind, hashtag_id, hashtag_name):
    return None


def send_custom(title, body, zone_id=None):
    return None


def send_custom_to(title, body, recipients):
    return None
