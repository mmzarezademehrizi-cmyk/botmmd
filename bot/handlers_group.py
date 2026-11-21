# -*- coding: utf-8 -*-
"""هندلر پیام‌های گروه، عضوگیری/خروج، پنل مدیریت گروه و callbackهای آن."""
import time
import threading
import html as _html
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from base import database as db
from features import media_store
from features import notifications
from base.core import (
    bot, _safe_handler, _update_activity, is_admin_or_owner, is_group_chat,
    get_state, set_state, clear_state, cur_state, state_data, _edit_panel,
    S_WAIT_GROUP_HASHTAG, S_WAIT_GROUP_CONTENT, S_WAIT_GROUP_NAME,
    S_WAIT_GROUP_REEL_CONTENT, S_WAIT_GROUP_STORY_CONTENT,
    S_WAIT_GROUP_HASHTAG_ZONE,
    set_ht_zone_selection, get_ht_zone_selection, toggle_ht_zone,
    set_ht_zones_all, clear_ht_zone_selection,
)
from bot.keyboards import (
    _group_panel_kb, _group_panel_text, _group_twitter_kb, _group_instagram_kb,
    _group_ht_select_kb, _group_no_tag_kb,
    _group_transfer_kb, _group_transfer_type_kb, _cancel_kb, _confirm_kb,
    _group_zone_pick_kb, ht_zone_select_kb,
)
from bot.texts import _ht_zone_select_text
from bot.admin_ops import _report_to_owner, update_all_admin_status_messages

def _send_group_panel(cid: int, mid: int = None):
    text = _group_panel_text(cid)
    kb   = _group_panel_kb()
    if mid:
        try:
            bot.edit_message_text(text, cid, mid, parse_mode='HTML', reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(cid, text, parse_mode='HTML', reply_markup=kb)

# ─────────────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────────────
import re

def _video_file_id(message):
    """
    فایل ویدیو رو چه به‌صورت content_type='video' فرستاده شده باشه (حالت
    عادی گالری/دوربین)، چه به‌صورت 'document' (وقتی از دسکتاپ یا با گزینه‌ی
    «فایل» فرستاده می‌شه - تلگرام گاهی ویدیوهای حجیم‌تر رو این‌جوری می‌فرسته)
    پیدا می‌کنه. اگه ویدیو نبود، None برمی‌گردونه.
    قبلاً فقط message.video چک می‌شد، برای همین ویدیوهایی که به‌صورت فایل
    فرستاده می‌شدن اصلاً قبول نمی‌شدن.
    """
    if message.content_type == 'video' and message.video:
        return message.video.file_id
    if message.content_type == 'document' and message.document:
        mime = (message.document.mime_type or '')
        if mime.startswith('video/'):
            return message.document.file_id
    return None

@bot.message_handler(
    func=lambda m: is_group_chat(m.chat.type),
    content_types=['text', 'photo', 'video', 'document']
)
@_safe_handler
def handle_group(message):
    uid  = message.from_user.id
    cid  = message.chat.id
    text = (message.text or message.caption or '').strip()
    video_fid = _video_file_id(message)
    _update_activity(uid)
    db.register_user(uid, message.from_user.username,
                     message.from_user.first_name, message.from_user.last_name)

    # ── تشخیص صریح استارت پنل گروه ────────────────────────────────────────
    # به‌جای تکیه به فیلتر commands=['start'] کتابخونه (که رفتارش با
    # /start@نام‌کاربری بین نسخه‌ها می‌تونه فرق کنه)، اینجا مستقیم و قطعی چک
    # می‌کنیم: /start ، /start@هرچی ، یا کلمه‌ی فارسی «استارت».
    if message.content_type == 'text' and re.match(r'^/start(@\w+)?$|^استارت$', text, re.IGNORECASE):
        if is_admin_or_owner(uid):
            _send_group_panel(cid)
        return

    cs = cur_state(uid, cid)
    # عکس در حالت content (توییتر) — عکس یا ویدیو، هرکدوم با نوع واقعی خودش ذخیره می‌شود
    #
    # نکته‌ی مهم (فیکس): قبلاً اینجا یه شرط اضافه بود
    # (state_data(uid, cid).get('media') == 'photo') که هیچ‌جای کد مقدار
    # 'media' ست نمی‌شد، پس این شرط همیشه False بود و عکس/ویدیو اصلاً به
    # این بلوک نمی‌رسید - در نتیجه اگه با کپشن می‌فرستادی، کپشن به‌اشتباه
    # به‌عنوان متن ذخیره می‌شد؛ بدون کپشن هم کلاً نادیده گرفته می‌شد.
    if (message.content_type == 'photo' or video_fid) and is_admin_or_owner(uid) and cs == S_WAIT_GROUP_CONTENT:
        sdata = state_data(uid, cid)
        hid   = sdata.get('hashtag_id')
        ht    = db.get_hashtag_by_id(hid) if hid else db.get_newest_hashtag()
        if ht:
            if message.content_type == 'photo':
                db.add_photo(message.photo[-1].file_id, ht['id'], media_type='photo')
                media_store.cache_async(message.photo[-1].file_id, 'photo')  # نسخه‌یِ دائمیِ رویِ سرور
            else:
                db.add_photo(video_fid, ht['id'], media_type='video')
                media_store.cache_async(video_fid, 'video')
            try:
                notifications.notify_content_available('photo', ht['id'], ht['name'])
            except Exception:
                pass
            try: bot.reply_to(message, f'✅ ذخیره شد زیر «{ht["name"]}»')
            except Exception: bot.send_message(cid, f'✅ ذخیره شد زیر «{ht["name"]}»')
        return

    # ریلز = ویدیو + کپشن (باید هر دو با هم باشن)
    if is_admin_or_owner(uid) and cs == S_WAIT_GROUP_REEL_CONTENT:
        sdata = state_data(uid, cid)
        hid   = sdata.get('hashtag_id')
        ht    = db.get_hashtag_by_id(hid) if hid else db.get_newest_hashtag()
        if not ht:
            bot.send_message(cid, '⚠️ هیچ هشتگی پیدا نشد.'); clear_state(uid, cid); return
        if video_fid:
            caption = (message.caption or '').strip()
            if not caption:
                bot.reply_to(message, '📝 کپشنش کو؟')
                return  # پیام پاک نمی‌شود، فقط منتظر کپشن/تلاش دوباره می‌مونه
            db.add_reel(video_fid, caption, ht['id'])
            media_store.cache_async(video_fid, 'video')
            db.set_setting('low_text_alert_sent', 'false')
            try:
                notifications.notify_content_available('reel', ht['id'], ht['name'])
            except Exception:
                pass
            try: bot.reply_to(message, f'✅ ریلز برای «{ht["name"]}» ذخیره شد.')
            except Exception: bot.send_message(cid, f'✅ ریلز برای «{ht["name"]}» ذخیره شد.')
            _report_to_owner(f'یک ریلز به «{ht["name"]}» اضافه شد توسط {message.from_user.first_name}')
            # state عمداً پاک نمی‌شود تا بشه چند ریلز پشت‌سرهم فرستاد؛ فقط با
            # دکمه‌ی «لغو» یا تایم‌اوت ۱۰ دقیقه‌ای غیرفعال می‌شود.
            return
        if message.content_type == 'text':
            bot.reply_to(message, '🎬 بدون فیلم اخه....')
            return
        return  # سایر انواع پیام در این state نادیده گرفته می‌شوند

    # استوری = عکس یا ویدیو، هرکدوم با نوع واقعی خودش ذخیره می‌شود
    if is_admin_or_owner(uid) and cs == S_WAIT_GROUP_STORY_CONTENT:
        sdata = state_data(uid, cid)
        hid   = sdata.get('hashtag_id')
        ht    = db.get_hashtag_by_id(hid) if hid else db.get_newest_hashtag()
        if not ht:
            bot.send_message(cid, '⚠️ هیچ هشتگی پیدا نشد.'); clear_state(uid, cid); return
        if message.content_type == 'photo' or video_fid:
            if message.content_type == 'photo':
                db.add_story(message.photo[-1].file_id, ht['id'], media_type='photo')
                media_store.cache_async(message.photo[-1].file_id, 'photo')
            else:
                db.add_story(video_fid, ht['id'], media_type='video')
                media_store.cache_async(video_fid, 'video')
            db.set_setting('low_text_alert_sent', 'false')
            try:
                notifications.notify_content_available('story', ht['id'], ht['name'])
            except Exception:
                pass
            try: bot.reply_to(message, f'✅ استوری برای «{ht["name"]}» ذخیره شد.')
            except Exception: bot.send_message(cid, f'✅ استوری برای «{ht["name"]}» ذخیره شد.')
            _report_to_owner(f'یک استوری به «{ht["name"]}» اضافه شد توسط {message.from_user.first_name}')
            # state عمداً پاک نمی‌شود تا بشه چند استوری پشت‌سرهم فرستاد (مثل ریلز)
        return

    if not text:
        return
    if cs == S_WAIT_GROUP_HASHTAG and is_admin_or_owner(uid):
        ht_text = text if text.startswith('#') else '#' + text.lstrip('#').strip()
        clear_state(uid, cid)
        set_ht_zone_selection(uid, cid, ht_text, True, [])
        bot.send_message(cid, _ht_zone_select_text(ht_text, 0, len(db.get_all_zones())),
                         parse_mode='HTML', reply_markup=ht_zone_select_kb([]))
        return
    if cs == S_WAIT_GROUP_CONTENT and is_admin_or_owner(uid):
        sdata = state_data(uid, cid)
        hid   = sdata.get('hashtag_id')
        ht    = db.get_hashtag_by_id(hid) if hid else db.get_newest_hashtag()
        if not ht:
            bot.send_message(cid, '⚠️ هیچ هشتگی پیدا نشد.')
            clear_state(uid, cid); return
        parts    = [p.strip() for p in text.split('﷼') if p.strip()]
        if not parts:
            bot.send_message(cid, '⚠️ هیچ متنی پیدا نشد.'); return
        append   = bool(ht.get('append_tag', 1))
        contents = [f'{p}\n{ht["name"]}' if append else p for p in parts]
        db.add_texts(contents, ht['id'])
        db.set_setting('low_text_alert_sent', 'false')
        try:
            notifications.notify_content_available('text', ht['id'], ht['name'])
        except Exception:
            pass
        count = len(contents)
        try: bot.delete_message(cid, message.message_id)
        except Exception: pass
        confirm_msg = bot.send_message(cid, f'{count} متن به ربات اضافه شد ✅')
        def _del_later():
            time.sleep(20)
            try: bot.delete_message(cid, confirm_msg.message_id)
            except Exception: pass
        threading.Thread(target=_del_later, daemon=True).start()
        update_all_admin_status_messages()
        _report_to_owner(f'{count} متن به «{ht["name"]}» اضافه شد توسط {message.from_user.first_name}')
        return
    if cs == S_WAIT_GROUP_NAME and is_admin_or_owner(uid):
        gname = text.strip()
        clear_state(uid, cid)
        set_ht_zone_selection(uid, cid, gname, False, [])
        bot.send_message(cid, _ht_zone_select_text(gname, 0, len(db.get_all_zones())),
                         parse_mode='HTML', reply_markup=ht_zone_select_kb([]))
        return

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    for m in message.new_chat_members:
        if m.id == bot.get_me().id:
            cid  = message.chat.id
            name = message.chat.title or str(cid)
            link = 'N/A'
            try:
                lo = bot.export_chat_invite_link(cid)
                if lo: link = lo
            except Exception: pass
            db.add_group(cid, name, link)
            bot.send_message(cid, 'سلام 👋')
            try:
                owner_id = db.get_owner_id()
                if owner_id:
                    bot.send_message(owner_id, f'ربات به گروه «{name}» اضافه شد 📢\nID: {cid}')
            except Exception: pass

@bot.message_handler(content_types=['left_chat_member'])
def handle_left_member(message):
    if message.left_chat_member.id == bot.get_me().id:
        db.remove_group(message.chat.id)

# ─────────────────────────────────────────────────────────────────────────────
# Callback query handler
# ─────────────────────────────────────────────────────────────────────────────
def _handle_group_callback(call, uid, cid, mid, data):
    bot.answer_callback_query(call.id)

    # مقصدهای «بازگشت/لغو» — همیشه باید state در حال انتظار (هشتگ/متن/عکس/
    # ریلز/استوری) را هم پاک کنند، وگرنه دکمه‌ی «❌ لغو» فقط پیام را عوض
    # می‌کرد ولی state هنوز فعال می‌ماند و پیام بعدی همچنان قبول می‌شد.
    if data in ('grp:back', 'grp:twitter', 'grp:instagram', 'grp:no_tag'):
        clear_state(uid, cid)

    if data == 'grp:back':
        _send_group_panel(cid, mid); return

    if data == 'grp:twitter':
        _edit_panel(cid, mid, '🐦 <b>مدیریت محتوای توییتر</b>', _group_twitter_kb(), parse_mode='HTML'); return

    if data == 'grp:instagram':
        _edit_panel(cid, mid, '📸 <b>مدیریت محتوای اینستاگرام</b>', _group_instagram_kb(), parse_mode='HTML'); return

    if data.startswith('grp:htzone:toggle:'):
        zid = int(data.split(':')[3])
        sel = toggle_ht_zone(uid, cid, zid)
        if not sel:
            _edit_panel(cid, mid, '⚠️ این درخواست منقضی شده، دوباره «➕ هشتگ» را بزنید.', InlineKeyboardMarkup()); return
        zones_total = len(db.get_all_zones())
        _edit_panel(cid, mid, _ht_zone_select_text(sel['ht_text'], len(sel['zone_ids']), zones_total),
                   ht_zone_select_kb(sel['zone_ids']))
        return

    if data == 'grp:htzone:toggle_all':
        sel = get_ht_zone_selection(uid, cid)
        if not sel:
            _edit_panel(cid, mid, '⚠️ این درخواست منقضی شده، دوباره «➕ هشتگ» را بزنید.', InlineKeyboardMarkup()); return
        all_zones = [z['id'] for z in db.get_all_zones()]
        select_all = len(sel['zone_ids']) < len(all_zones)
        sel = set_ht_zones_all(uid, cid, all_zones, select_all)
        _edit_panel(cid, mid, _ht_zone_select_text(sel['ht_text'], len(sel['zone_ids']), len(all_zones)),
                   ht_zone_select_kb(sel['zone_ids']))
        return

    if data == 'grp:htzone:confirm':
        sel = get_ht_zone_selection(uid, cid)
        if not sel:
            _edit_panel(cid, mid, '⚠️ این درخواست منقضی شده، دوباره «➕ هشتگ» را بزنید.', InlineKeyboardMarkup()); return
        clear_ht_zone_selection(uid, cid)
        hid = db.add_hashtag(sel['ht_text'], append_tag=sel['append_tag'])
        db.set_hashtag_zones(hid, list(sel['zone_ids']))
        if sel['zone_ids']:
            names = '، '.join(z['name'] for z in db.get_all_zones() if z['id'] in sel['zone_ids'])
            scope = f'برای ناحیه‌های: {names}'
        else:
            scope = 'برای همه‌ی ناحیه‌ها'
        kind = 'هشتگ' if sel['append_tag'] else 'گروه بدون هشتگ'
        _edit_panel(cid, mid, f'✅ {kind} «{sel["ht_text"]}» ثبت شد ({scope}).', InlineKeyboardMarkup())
        _report_to_owner(f'{kind} «{sel["ht_text"]}» اضافه شد ({scope}).')
        return

    if data == 'grp:add_hashtag':
        set_state(uid, cid, S_WAIT_GROUP_HASHTAG)
        _edit_panel(cid, mid, '🏷 هشتگ جدید را وارد کنید:', _cancel_kb('grp:back')); return

    if data == 'grp:del_hashtag':
        _edit_panel(cid, mid, '🏷 کدام هشتگ را حذف کنید؟', _group_ht_select_kb('grp:del_ht_confirm')); return

    if data.startswith('grp:del_ht_confirm:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        _edit_panel(cid, mid, f'تمام محتوای «{ht["name"]}» حذف می‌شود. مطمئنید؟',
                    _confirm_kb(f'grp:del_ht_do:{hid}', 'grp:back')); return

    if data.startswith('grp:del_ht_do:'):
        hid  = int(data.split(':')[2])
        ht   = db.get_hashtag_by_id(hid)
        name = ht['name'] if ht else str(hid)
        db.delete_hashtag(hid)
        update_all_admin_status_messages()
        _report_to_owner(f'هشتگ «{name}» حذف شد')
        try: bot.edit_message_text(f'✅ هشتگ «{name}» حذف شد.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return

    if data == 'grp:add_text':
        _edit_panel(cid, mid, '📝 هشتگ مقصد را انتخاب کنید:',
                    _group_ht_select_kb('grp:sel_ht_for_text', 'grp:twitter')); return

    if data.startswith('grp:sel_ht_for_text:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        set_state(uid, cid, S_WAIT_GROUP_CONTENT, hashtag_id=hid)
        _edit_panel(cid, mid,
            f'📍 «{_html.escape(ht["name"])}» انتخاب شد.\nمتن‌ها را با ﷼ جدا کنید.\n⏱ بعد ۱۰ دقیقه بی‌فعالیتی غیرفعال می‌شود.',
            _cancel_kb('grp:twitter')); return

    if data == 'grp:del_text':
        _edit_panel(cid, mid, '📝 متن‌های کدام هشتگ را حذف کنید؟',
                    _group_ht_select_kb('grp:del_text_confirm', 'grp:twitter')); return

    if data.startswith('grp:del_text_confirm:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        tc = db.count_texts_by_hashtag(hid)
        _edit_panel(cid, mid, f'«{ht["name"]}» دارای {tc} متن است. همه حذف شوند؟',
                    _confirm_kb(f'grp:del_text_do:{hid}', 'grp:twitter')); return

    if data.startswith('grp:del_text_do:'):
        hid  = int(data.split(':')[2])
        ht   = db.get_hashtag_by_id(hid)
        name = ht['name'] if ht else str(hid)
        db.delete_texts_by_hashtag(hid)
        update_all_admin_status_messages()
        _report_to_owner(f'متن‌های «{name}» حذف شدند')
        try: bot.edit_message_text(f'✅ متن‌های «{name}» حذف شدند.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return

    if data == 'grp:add_photo':
        _edit_panel(cid, mid, '🖼 هشتگ مقصد را انتخاب کنید:',
                    _group_ht_select_kb('grp:sel_ht_for_photo', 'grp:twitter')); return

    if data.startswith('grp:sel_ht_for_photo:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        set_state(uid, cid, S_WAIT_GROUP_CONTENT, hashtag_id=hid)
        _edit_panel(cid, mid, f'📍 «{_html.escape(ht["name"])}» انتخاب شد.\nعکس یا ویدیو ارسال کنید.',
                    _cancel_kb('grp:twitter')); return

    if data == 'grp:del_photo':
        _edit_panel(cid, mid, '🖼 عکس‌های کدام هشتگ را حذف کنید؟',
                    _group_ht_select_kb('grp:del_photo_confirm', 'grp:twitter')); return

    if data.startswith('grp:del_photo_confirm:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        pc = db.count_photos_by_hashtag(hid)
        _edit_panel(cid, mid, f'«{ht["name"]}» دارای {pc} عکس/ویدیو است. همه حذف شوند؟',
                    _confirm_kb(f'grp:del_photo_do:{hid}', 'grp:twitter')); return

    if data.startswith('grp:del_photo_do:'):
        hid  = int(data.split(':')[2])
        ht   = db.get_hashtag_by_id(hid)
        name = ht['name'] if ht else str(hid)
        db.delete_photos_by_hashtag(hid)
        _report_to_owner(f'عکس‌های «{name}» حذف شدند')
        try: bot.edit_message_text(f'✅ عکس‌های «{name}» حذف شدند.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return

    # ── ریلز ──────────────────────────────────────────────────────────────
    if data == 'grp:add_reel':
        _edit_panel(cid, mid, 'لطفا مخزن را انتخاب کنید:',
                    _group_ht_select_kb('grp:sel_ht_for_reel', 'grp:instagram')); return

    if data.startswith('grp:sel_ht_for_reel:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        set_state(uid, cid, S_WAIT_GROUP_REEL_CONTENT, hashtag_id=hid)
        _edit_panel(cid, mid,
            f'🎬 ریلز را برای «{_html.escape(ht["name"])}» بفرستید (ویدیو + کپشن).\n'
            '⏱ بعد ۱۰ دقیقه بی‌فعالیتی غیرفعال می‌شود.',
            _cancel_kb('grp:instagram')); return

    if data == 'grp:del_reel':
        _edit_panel(cid, mid, '🎬 ریلزهای کدام هشتگ را حذف کنید؟',
                    _group_ht_select_kb('grp:del_reel_confirm', 'grp:instagram')); return

    if data.startswith('grp:del_reel_confirm:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        rc = db.count_reels_by_hashtag(hid)
        _edit_panel(cid, mid, f'«{ht["name"]}» دارای {rc} ریلز است. همه حذف شوند؟',
                    _confirm_kb(f'grp:del_reel_do:{hid}', 'grp:instagram')); return

    if data.startswith('grp:del_reel_do:'):
        hid  = int(data.split(':')[2])
        ht   = db.get_hashtag_by_id(hid)
        name = ht['name'] if ht else str(hid)
        db.delete_reels_by_hashtag(hid)
        _report_to_owner(f'ریلزهای «{name}» حذف شدند')
        try: bot.edit_message_text(f'✅ ریلزهای «{name}» حذف شدند.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return

    # ── استوری ────────────────────────────────────────────────────────────
    if data == 'grp:add_story':
        _edit_panel(cid, mid, 'لطفا مخزن را انتخاب کنید:',
                    _group_ht_select_kb('grp:sel_ht_for_story', 'grp:instagram')); return

    if data.startswith('grp:sel_ht_for_story:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        set_state(uid, cid, S_WAIT_GROUP_STORY_CONTENT, hashtag_id=hid)
        _edit_panel(cid, mid,
            f'⭕️ استوری را برای «{_html.escape(ht["name"])}» بفرستید (عکس یا ویدیو).\n'
            '⏱ بعد ۱۰ دقیقه بی‌فعالیتی غیرفعال می‌شود.',
            _cancel_kb('grp:instagram')); return

    if data == 'grp:del_story':
        _edit_panel(cid, mid, '⭕️ استوری‌های کدام هشتگ را حذف کنید؟',
                    _group_ht_select_kb('grp:del_story_confirm', 'grp:instagram')); return

    if data.startswith('grp:del_story_confirm:'):
        hid = int(data.split(':')[2])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: _send_group_panel(cid, mid); return
        sc = db.count_stories_by_hashtag(hid)
        _edit_panel(cid, mid, f'«{ht["name"]}» دارای {sc} استوری است. همه حذف شوند؟',
                    _confirm_kb(f'grp:del_story_do:{hid}', 'grp:instagram')); return

    if data.startswith('grp:del_story_do:'):
        hid  = int(data.split(':')[2])
        ht   = db.get_hashtag_by_id(hid)
        name = ht['name'] if ht else str(hid)
        db.delete_stories_by_hashtag(hid)
        _report_to_owner(f'استوری‌های «{name}» حذف شدند')
        try: bot.edit_message_text(f'✅ استوری‌های «{name}» حذف شدند.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return

    if data == 'grp:no_tag':
        _edit_panel(cid, mid, '📁 <b>گروه‌های بدون هشتگ:</b>', _group_no_tag_kb(), parse_mode='HTML'); return

    if data == 'grp:add_no_tag':
        set_state(uid, cid, S_WAIT_GROUP_NAME)
        _edit_panel(cid, mid, '📁 اسم گروه جدید را وارد کنید:', _cancel_kb('grp:no_tag')); return

    if data == 'grp:del_no_tag_list':
        groups = db.get_no_tag_groups()
        if not groups:
            _edit_panel(cid, mid, '📁 هیچ گروهی برای حذف وجود ندارد.', _cancel_kb('grp:no_tag')); return
        kb = InlineKeyboardMarkup(row_width=1)
        for g in groups:
            kb.add(InlineKeyboardButton(f'❌ {g["name"]}', callback_data=f'grp:del_notag_confirm:{g["id"]}'))
        kb.add(InlineKeyboardButton('⬅️ برگشت', callback_data='grp:no_tag'))
        _edit_panel(cid, mid, 'کدام گروه را حذف کنید؟', kb); return

    if data.startswith('grp:del_notag_confirm:'):
        gid = int(data.split(':')[2])
        g   = db.get_hashtag_by_id(gid)
        if not g: _send_group_panel(cid, mid); return
        _edit_panel(cid, mid, f'گروه «{g["name"]}» با تمام محتوایش حذف می‌شود. مطمئنید؟',
                    _confirm_kb(f'grp:del_notag_do:{gid}', 'grp:no_tag')); return

    if data.startswith('grp:del_notag_do:'):
        gid  = int(data.split(':')[2])
        g    = db.get_hashtag_by_id(gid)
        name = g['name'] if g else str(gid)
        db.delete_hashtag(gid)
        _report_to_owner(f'گروه بدون هشتگ «{name}» حذف شد')
        try: bot.edit_message_text(f'✅ گروه «{name}» حذف شد.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return

    if data in ('grp:transfer_twitter', 'grp:transfer_instagram'):
        domain = 'twitter' if data.endswith('twitter') else 'instagram'
        _edit_panel(cid, mid, '🔀 نوع انتقال را انتخاب کنید:', _group_transfer_kb(domain)); return

    if data.startswith('grp:transfer:'):
        parts = data.split(':')
        domain, mode = parts[2], parts[3]
        _edit_panel(cid, mid,
            f'چه محتوایی {"کپی" if mode=="copy" else "منتقل"} شود؟',
            _group_transfer_type_kb(domain, mode)); return

    if data.startswith('grp:tr_type:'):
        parts = data.split(':')
        domain, mode, ctype = parts[2], parts[3], parts[4]
        _edit_panel(cid, mid, 'هشتگ مبدأ را انتخاب کنید:',
                    _group_ht_select_kb(f'grp:tr_src:{domain}:{mode}:{ctype}', f'grp:transfer_{domain}')); return

    if data.startswith('grp:tr_src:'):
        parts = data.split(':')
        domain, mode, ctype, src_hid = parts[2], parts[3], parts[4], int(parts[5])
        _edit_panel(cid, mid, 'هشتگ مقصد را انتخاب کنید:',
                    _group_ht_select_kb(f'grp:tr_dst:{domain}:{mode}:{ctype}:{src_hid}', f'grp:transfer_{domain}')); return

    if data.startswith('grp:tr_dst:'):
        parts = data.split(':')
        domain, mode, ctype, src_hid, dst_hid = parts[2], parts[3], parts[4], int(parts[5]), int(parts[6])
        src_ht  = db.get_hashtag_by_id(src_hid)
        dst_ht  = db.get_hashtag_by_id(dst_hid)
        if not src_ht or not dst_ht: _send_group_panel(cid, mid); return
        moved   = db.transfer_content(src_hid, dst_hid, ctype, cut=(mode == 'cut'))
        action  = 'منتقل' if mode == 'cut' else 'کپی'
        fa      = {'text': 'متن', 'photo': 'عکس', 'reel': 'ریلز', 'story': 'استوری',
                   'all': 'محتوا', 'all_ig': 'محتوا'}.get(ctype, ctype)
        _report_to_owner(f'{moved} {fa} از «{src_ht["name"]}» به «{dst_ht["name"]}» {action} شد')
        update_all_admin_status_messages()
        try: bot.edit_message_text(f'✅ {moved} {fa} {action} شد.', cid, mid)
        except Exception: pass
        time.sleep(1); _send_group_panel(cid, mid); return


# ─────────────────────────────────────────────────────────────────────────────
# Catch-all
# ─────────────────────────────────────────────────────────────────────────────
