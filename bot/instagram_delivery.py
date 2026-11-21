# -*- coding: utf-8 -*-
"""
تحویل محتوای اینستاگرام (ریلز و استوری) به کاربر.

فرق اصلی با content_delivery.py (متن/عکس توییتر):
    - ریلز/استوری هرگز از مخزن حذف نمی‌شوند (فقط برای هر کاربر یک‌بار مصرف
      می‌شوند، از طریق جدول‌های user_received_reels/user_received_stories).
    - محدودیت تعداد + ساعت برای ریلز و استوری کاملاً جدا از هم و جدا از
      توییتر است (reel_limit/reel_cooldown_hours و story_limit/story_cooldown_hours).
    - وقتی کاربر همه‌ی محتوای یکتای یک هشتگ را گرفته باشد، پیام «تمام محتوا را
      دریافت کردید» می‌بیند و دیگر چیزی برایش نمی‌آید — مگر ادمین محتوای تازه
      اضافه کند.
"""
from datetime import datetime

from base import database as db
from base.core import bot, is_owner, is_bot_admin_or_owner, format_wait_time
from bot.keyboards import _user_ht_reel_kb, _user_ht_story_kb
from bot.admin_ops import update_all_admin_status_messages
from bot.content_delivery import _require_panel_login


def _empty_repo_report(kind_label: str, hashtag_name: str):
    """گزارش خودکار به owner و همه‌ی bot adminها وقتی مخزن یک نوع محتوا خالی است."""
    try:
        owner_id = db.get_owner_id()
        if owner_id:
            bot.send_message(
                owner_id,
                f'⚠️ کاربران درخواست دریافت {kind_label} برای هشتگ «{hashtag_name}» را دارند '
                'ولی خالی بود.\nلطفا زودی پرش کنید.'
            )
        for a in db.get_all_bot_admins():
            try:
                bot.send_message(
                    a['user_id'],
                    f'⚠️ کاربران درخواست دریافت {kind_label} برای هشتگ «{hashtag_name}» را دارند '
                    'ولی خالی بود.\nلطفا زودی پرش کنید.'
                )
            except Exception:
                pass
    except Exception:
        pass


def _deliver_reel(uid, cid, hid, count: int = 1, zone_id=None, panel_user_id=None):
    total = db.count_reels_by_hashtag(hid)
    if total == 0:
        ht = db.get_hashtag_by_id(hid)
        bot.send_message(cid, 'بنده خالی از محتوای ریلز هستم.\nگزارش خالی بودن محتوا برای ادمین ارسال شد.')
        _empty_repo_report('ریلز', ht['name'] if ht else '؟')
        return

    privileged = is_bot_admin_or_owner(uid) or db.is_instagram_vip_user(uid)
    delivered  = 0
    for _ in range(max(1, count)):
        reel = db.get_unreceived_reel(uid, hid)
        if not reel:
            if delivered == 0:
                bot.send_message(cid, 'شما تمام ریلز های این هشتگ را دریافت کرده‌اید 🔄')
            break

        if not privileged:
            allowance  = db.get_reel_limit(zone_id)
            cooldown_h = db.get_reel_cooldown_hours(zone_id)
            remaining, locked_until = db.check_content_cooldown(uid, 'reel', allowance, cooldown_h)
            if remaining <= 0:
                if delivered == 0:
                    wait_str  = format_wait_time(locked_until) if locked_until else '?'
                    lock_tmpl = db.get_zone_setting(zone_id, 'lock_msg', None) or (
                        '🚫 دسترسی موقت مسدود شد\n⏳ زمان باقی‌مانده: {time}'
                    )
                    bot.send_message(cid, lock_tmpl.replace('{time}', wait_str))
                break

        bot.send_video(cid, reel['file_id'], caption=reel.get('caption') or '')
        db.mark_reel_received(uid, reel['id'])
        if panel_user_id is not None:
            db.add_content_history(
                -panel_user_id, "reel", hashtag_id=hid, media_type="video",
                ref_id=reel['id'], caption=reel.get('caption'), platform='bot',
            )
        if not privileged:
            db.update_content_cooldown(uid, 'reel', 1, db.get_reel_cooldown_hours(zone_id))
        delivered += 1


def _deliver_story(uid, cid, hid, count: int = 1, zone_id=None, panel_user_id=None):
    total = db.count_stories_by_hashtag(hid)
    if total == 0:
        ht = db.get_hashtag_by_id(hid)
        bot.send_message(cid, 'بنده خالی از محتوای استوری هستم.\nگزارش خالی بودن محتوا برای ادمین ارسال شد.')
        _empty_repo_report('استوری', ht['name'] if ht else '؟')
        return

    privileged = is_bot_admin_or_owner(uid) or db.is_instagram_vip_user(uid)
    delivered  = 0
    for _ in range(max(1, count)):
        story = db.get_unreceived_story(uid, hid)
        if not story:
            if delivered == 0:
                bot.send_message(cid, 'شما تمام استوری های این هشتگ را دریافت کرده‌اید 🔄')
            break

        if not privileged:
            allowance  = db.get_story_limit(zone_id)
            cooldown_h = db.get_story_cooldown_hours(zone_id)
            remaining, locked_until = db.check_content_cooldown(uid, 'story', allowance, cooldown_h)
            if remaining <= 0:
                if delivered == 0:
                    wait_str  = format_wait_time(locked_until) if locked_until else '?'
                    lock_tmpl = db.get_zone_setting(zone_id, 'lock_msg', None) or (
                        '🚫 دسترسی موقت مسدود شد\n⏳ زمان باقی‌مانده: {time}'
                    )
                    bot.send_message(cid, lock_tmpl.replace('{time}', wait_str))
                break

        if story.get('media_type') == 'video':
            try:
                bot.send_video(cid, story['file_id'])
            except Exception as e:
                msg = str(e)
                if 'as Video' in msg or 'as Photo' in msg or 'wrong file identifier' in msg.lower():
                    bot.send_photo(cid, story['file_id'])
                    db.fix_story_media_type(story['id'], 'photo')
                else:
                    raise
        else:
            try:
                bot.send_photo(cid, story['file_id'])
            except Exception as e:
                msg = str(e)
                if 'as Video' in msg or 'as Photo' in msg or 'wrong file identifier' in msg.lower():
                    bot.send_video(cid, story['file_id'])
                    db.fix_story_media_type(story['id'], 'video')
                else:
                    raise
        db.mark_story_received(uid, story['id'])
        if panel_user_id is not None:
            db.add_content_history(
                -panel_user_id, "story", hashtag_id=hid,
                media_type=story.get('media_type', 'photo'), ref_id=story['id'], platform='bot',
            )
        if not privileged:
            db.update_content_cooldown(uid, 'story', 1, db.get_story_cooldown_hours(zone_id))
        delivered += 1


def handle_reel_request(message, count: int = 1):
    uid, cid = message.from_user.id, message.chat.id
    if not db.is_operation_active():
        bot.send_message(cid, 'عملیاتی در جریان نیست.')
        return
    pu = _require_panel_login(uid, cid)
    if pu is None:
        return
    zone_id = pu['zone_id']
    active_hts = db.get_active_hashtags_for_zone(zone_id)
    if not active_hts:
        bot.send_message(cid, 'هیچ هشتگی فعال نیست.')
        return
    if len(active_hts) > 1:
        bot.send_message(cid, 'لطفا هشتگ مورد نظر را انتخاب کنید.', reply_markup=_user_ht_reel_kb(zone_id))
        return
    _deliver_reel(uid, cid, active_hts[0]['id'], count=count, zone_id=zone_id, panel_user_id=pu.get('id'))


def handle_story_request(message, count: int = 1):
    uid, cid = message.from_user.id, message.chat.id
    if not db.is_operation_active():
        bot.send_message(cid, 'عملیاتی در جریان نیست.')
        return
    pu = _require_panel_login(uid, cid)
    if pu is None:
        return
    zone_id = pu['zone_id']
    active_hts = db.get_active_hashtags_for_zone(zone_id)
    if not active_hts:
        bot.send_message(cid, 'هیچ هشتگی فعال نیست.')
        return
    if len(active_hts) > 1:
        bot.send_message(cid, 'لطفا هشتگ مورد نظر را انتخاب کنید.', reply_markup=_user_ht_story_kb(zone_id))
        return
    _deliver_story(uid, cid, active_hts[0]['id'], count=count, zone_id=zone_id, panel_user_id=pu.get('id'))


def _send_instagram_status(uid: int, cid: int):
    if is_owner(uid):
        role, info = '👑 مالک ربات', '⚡️ محدودیت: ندارید'
    elif db.is_bot_admin(uid):
        role, info = '🛡 ادمین ربات', '⚡️ محدودیت: ندارید'
    elif db.is_instagram_vip_user(uid):
        role, info = '⭐️ کاربر VIP', '⚡️ محدودیت: ندارید'
    else:
        role = '👤 کاربر'
        zone_id = db.get_user_zone_id(uid)
        r_remaining, r_locked = db.check_content_cooldown(uid, 'reel', db.get_reel_limit(zone_id), db.get_reel_cooldown_hours(zone_id))
        s_remaining, s_locked = db.check_content_cooldown(uid, 'story', db.get_story_limit(zone_id), db.get_story_cooldown_hours(zone_id))
        r_received = db.get_reel_limit(zone_id) - r_remaining
        s_received = db.get_story_limit(zone_id) - s_remaining
        lines = [f'ریلز دریافت شده: {r_received} تا']
        if r_locked and datetime.utcnow() < r_locked:
            lines.append(f'وضعیت ریلز: 🔒 قفل تا {format_wait_time(r_locked)}')
        else:
            lines.append(f'باقی‌مانده ریلز: {r_remaining} تا')
        lines.append(f'استوری دریافت شده: {s_received} تا')
        if s_locked and datetime.utcnow() < s_locked:
            lines.append(f'وضعیت استوری: 🔒 قفل تا {format_wait_time(s_locked)}')
        else:
            lines.append(f'باقی‌مانده استوری: {s_remaining} تا')
        info = '\n'.join(lines)
    bot.send_message(cid, f'📊 <b>وضعیت شما در پنل محتوای اینستاگرام:</b>\n\nنقش: {role}\n{info}',
                     parse_mode='HTML')
