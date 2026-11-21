# -*- coding: utf-8 -*-
"""دیسپچر اصلی همه‌ی دکمه‌های شیشه‌ای (Inline) ربات."""
import html as _html
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from base import database as db
from base.core import (
    bot, log, _safe_handler, is_owner, is_bot_admin_or_owner, is_admin_or_owner,
    commander_pu,
    set_state, clear_state, cur_state, state_data, _edit_panel,
    set_admin_zone_ctx, get_admin_zone_ctx,
    set_people_selection, get_people_selection, toggle_people_zone,
    set_people_zones_all, clear_people_selection,
    init_export_selection, get_export_selection, toggle_export_zone,
    set_export_zones_all, clear_export_selection,
    S_WAIT_ADMIN_ID, S_WAIT_BOT_ADMIN_ID, S_WAIT_ADMIN_CONTACT,
    S_WAIT_END_OP_MSG, S_WAIT_GROUP_CONTENT, S_WAIT_INSTAGRAM_WELCOME_MSG,
    S_WAIT_FLOOD_MSG, S_WAIT_QUICK_ACCESS_MSG,
    S_WAIT_LIMIT_HOURS, S_WAIT_LIMIT_TEXTS, S_WAIT_LOCK_MSG,
    S_WAIT_LIMIT_REEL_COUNT, S_WAIT_LIMIT_REEL_HOURS,
    S_WAIT_LIMIT_STORY_COUNT, S_WAIT_LIMIT_STORY_HOURS,
    S_WAIT_START_OP_MSG, S_WAIT_TWITTER_WELCOME_MSG, S_WAIT_VIP_ID,
    S_WAIT_INSTAGRAM_VIP_ID, S_WAIT_WEBSITE_URL, S_WAIT_WELCOME_MSG,
    S_WAIT_PU_LOGIN_USERNAME, S_WAIT_ZONE_NAME,
    S_WAIT_ADMIN_PU_ZONE, S_WAIT_ADMIN_PU_USERNAME, S_WAIT_PEOPLE_USERNAME,
    S_WAIT_ADMIN_XLSX_FILE, S_WAIT_ADMIN_XLSX_ZONE_PICK, S_WAIT_ADMIN_BULK_COUNT,
    S_WAIT_CMD_PU_USERNAME, S_WAIT_CMD_ZONE_NAME,
)

# سقفِ سختِ ساختِ دسته‌ای - باید با _MAX_BULK_CREATE تویِ web_app.py یکی
# بمونه (اونجا برایِ اپ/سایته، اینجا برایِ بات).
_MAX_BULK_CREATE = 500
from bot.keyboards import (
    owner_settings_keyboard, confirm_delete_hashtag_kb, _btn_home, _btn_back,
    _status_kb, _limit_kb, _limit_twitter_kb, _limit_instagram_kb,
    _limit_reel_kb, _limit_story_kb, _limit_input_kb, _groups_kb, _groups_empty_kb,
    _group_admins_kb, _group_admins_remove_kb, _bot_admins_kb,
    _bot_admins_remove_kb, _website_kb, _website_change_url_kb,
    _msg_settings_kb, _msg_edit_kb, _vip_kb, _vip_twitter_kb, _vip_remove_kb,
    _instagram_vip_kb, _instagram_vip_remove_kb,
    _hashtag_start_op_kb, _hashtag_toggle_kb, _user_ht_photo_kb,
    account_menu_kb, owner_zones_kb, zone_detail_kb, zone_delete_confirm_kb,
    panel_user_detail_kb, panel_user_delete_confirm_kb, zone_pick_kb, login_required_kb,
    username_candidates_kb, people_list_kb, people_zone_select_kb, supervisor_zones_kb,
    zone_services_kb, puser_services_kb,
    commander_zones_kb, commander_zone_detail_kb, commander_puser_detail_kb,
    commander_puser_remove_confirm_kb, export_menu_kb, export_zone_select_kb,
)
from features import excel_tools
import io as _io
from telebot.types import InputFile
from bot.texts import (
    _settings_main_text, _status_text, _limit_text, _limit_twitter_text,
    _limit_instagram_text, _limit_reel_text, _limit_story_text, _groups_text,
    _bot_admins_text, _vip_text, _instagram_vip_text, _website_text, _group_admins_text,
    _msg_settings_text, _hashtag_access_text,
    _account_text, _zones_admin_text, _zone_detail_text, _panel_user_detail_text,
    _zone_services_text, _puser_services_text,
    _commander_zones_text, _commander_zone_detail_text, _commander_puser_detail_text,
    _people_list_text, _people_zone_select_text, _supervised_users_text,
    _ht_zone_select_text, get_msg_field,
)
from bot.content_delivery import (
    _deliver_texts_from_hashtag, _deliver_photos_batch, handle_text_request,
    handle_photo_request, _require_panel_login,
)
from bot.instagram_delivery import _deliver_reel, _deliver_story, handle_reel_request, handle_story_request
from bot.admin_ops import (
    _do_start_operation, _owner_stop_operation, _owner_backup, _report_to_owner,
    update_all_admin_status_messages, _reset_user_commands,
    update_admin_status_msg, _set_admin_commands,
)
from bot.handlers_group import _handle_group_callback

@bot.callback_query_handler(func=lambda c: True)
@_safe_handler
def handle_callback(call):
    uid  = call.from_user.id
    cid  = call.message.chat.id
    mid  = call.message.message_id
    data = call.data

    if data == 'noop':
        bot.answer_callback_query(call.id); return

    # فازِ ۶۳: تأییدِ ورود از لینکِ اپ (پیش از clear_state سراسری)
    if data.startswith('bl:'):
        from bot import bot_link
        bot_link.handle_callback(call); return

    # گروه‌ها را قبل از clear_state سراسری دیسپچ می‌کنیم چون بعضی کال‌بک‌های
    # گروه (مثل انتخاب ناحیه‌ی هشتگ) باید state ای که با تایپ متن ست شده رو
    # بخونن؛ اگه اینجا زودتر پاک بشه، دیتای در انتظار (مثلاً متن هشتگ) از
    # دست می‌ره و کاربر با خطای «درخواست منقضی شده» مواجه می‌شه.
    if data.startswith('grp:'):
        if not is_admin_or_owner(uid):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        _handle_group_callback(call, uid, cid, mid, data); return

    # هر بار که کاربر روی هر دکمه‌ی شیشه‌ای‌ای می‌زند (چه بازگشت، چه هرچیز
    # دیگر)، یعنی از هر state در انتظار متن (مثلاً منتظر آیدی عددی، پیام
    # جدید، و غیره) صرف‌نظر کرده — پس همیشه پاک می‌شود. اگر همین دکمه خودش
    # قرار است یک state جدید ست کند، آن ست‌کردن بعد از این خط انجام می‌شود و
    # مشکلی ایجاد نمی‌کند.
    clear_state(uid, cid)

    if data.startswith('quick:'):
        kind = data.split(':')[1]
        bot.answer_callback_query(call.id)
        # پیام فیک با همون chat/from_user برای استفاده مجدد از توابع تحویل موجود
        fake_msg = call.message
        fake_msg.from_user = call.from_user
        if kind == 'text':
            handle_text_request(fake_msg, 1)
        elif kind == 'photo':
            handle_photo_request(uid, cid)
        elif kind == 'reel':
            handle_reel_request(fake_msg, 1)
        elif kind == 'story':
            handle_story_request(fake_msg, 1)
        return

    if data == 'owner:home':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _settings_main_text(), owner_settings_keyboard()); return

    if data == 'owner:start_op':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        if not db.get_all_hashtags(): bot.answer_callback_query(call.id, '⚠️ هیچ هشتگی ثبت نشده.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '🚀 هشتگ مورد نظر را انتخاب کنید:', _hashtag_start_op_kb()); return

    if data.startswith('start_op_ht:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        hid = int(data.split(':')[1])
        if not db.get_hashtag_by_id(hid): bot.answer_callback_query(call.id, 'هشتگ یافت نشد.'); return
        bot.answer_callback_query(call.id, 'عملیات شروع شد ✅')
        _do_start_operation(cid, hid); return

    if data == 'owner:stop_op':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id, 'عملیات متوقف شد 🛑')
        _owner_stop_operation(cid); return

    if data == 'owner:backup':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id, 'در حال آماده‌سازی...')
        _owner_backup(cid); return

    if data == 'owner:status':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _status_text(), _status_kb()); return

    if data == 'owner:limit':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zones = db.get_all_zones()
        if not zones:
            bot.answer_callback_query(call.id, 'ابتدا حداقل یک ناحیه بسازید.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📁 محدودیت‌های کدام ناحیه را می‌خواهید تنظیم کنید؟', zone_pick_kb('limitzone')); return

    if data.startswith('limitzone:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid  = int(data.split(':')[1])
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        set_admin_zone_ctx(uid, cid, zid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _limit_text(zone['name']), _limit_kb(zid)); return

    if data == 'owner:limit_twitter':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _limit_twitter_text(zid), _limit_twitter_kb(zid)); return

    if data == 'owner:limit_instagram':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _limit_instagram_text(zid), _limit_instagram_kb(zid)); return

    if data == 'owner:limit_reel':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _limit_reel_text(zid), _limit_reel_kb(zid)); return

    if data == 'owner:limit_story':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _limit_story_text(zid), _limit_story_kb(zid)); return

    if data == 'limit:texts':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        set_state(uid, cid, S_WAIT_LIMIT_TEXTS)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid,
            f'⚙️ <b>تغییر سقف متن</b>\n\nمحدودیت فعلی: <b>{db.get_text_allowance(zid)}</b> تا\n\nعدد جدید:',
            _limit_input_kb('owner:limit_twitter')); return

    if data == 'limit:hours':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        set_state(uid, cid, S_WAIT_LIMIT_HOURS)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid,
            f'⚙️ <b>تغییر مدت قفل</b>\n\nمحدودیت فعلی: <b>{db.get_cooldown_hours(zid)}</b> ساعت\n\nعدد جدید:',
            _limit_input_kb('owner:limit_twitter')); return

    if data == 'limit:reel_count':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        set_state(uid, cid, S_WAIT_LIMIT_REEL_COUNT)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid,
            f'🎬 <b>تغییر تعداد دریافت ریلز</b>\n\n{db.get_reel_limit(zid)} تا قبلا بوده، لطفا عدد جدید را بگو:',
            _limit_input_kb('owner:limit_reel')); return

    if data == 'limit:reel_hours':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        set_state(uid, cid, S_WAIT_LIMIT_REEL_HOURS)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid,
            f'🎬 <b>تغییر محدودیت ساعت ریلز</b>\n\n{db.get_reel_cooldown_hours(zid)} ساعت قبلا بوده، عدد جدید:',
            _limit_input_kb('owner:limit_reel')); return

    if data == 'limit:story_count':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        set_state(uid, cid, S_WAIT_LIMIT_STORY_COUNT)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid,
            f'⭕️ <b>تغییر تعداد دریافت استوری</b>\n\n{db.get_story_limit(zid)} تا قبلا بوده، لطفا عدد جدید را بگو:',
            _limit_input_kb('owner:limit_story')); return

    if data == 'limit:story_hours':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = get_admin_zone_ctx(uid, cid)
        set_state(uid, cid, S_WAIT_LIMIT_STORY_HOURS)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid,
            f'⭕️ <b>تغییر محدودیت ساعت استوری</b>\n\n{db.get_story_cooldown_hours(zid)} ساعت قبلا بوده، عدد جدید:',
            _limit_input_kb('owner:limit_story')); return

    if data == 'owner:groups':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        groups = db.get_all_groups()
        _edit_panel(cid, mid, _groups_text(), _groups_kb() if groups else _groups_empty_kb(),
                    parse_mode=None); return

    if data == 'owner:group_admins':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        bot.answer_callback_query(call.id)
        admins = db.get_all_group_admins()
        body   = '\n'.join(f'• {_html.escape(a.get("first_name") or str(a["user_id"]))} (ID: {a["user_id"]})' for a in admins) if admins else 'هیچ ادمین گروهی وجود ندارد.'
        _edit_panel(cid, mid, f'👥 <b>ادمین‌های گروه:</b>\n{body}', _group_admins_kb()); return

    if data == 'owner:remove_admin_list':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '👥 کدام ادمین را حذف کنید؟', _group_admins_remove_kb()); return

    if data.startswith('ppick:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        _, action, pu_id_str = data.split(':')
        pu = db.get_panel_user(int(pu_id_str))
        if not pu:
            bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        if not pu.get('telegram_user_id'):
            bot.answer_callback_query(call.id, 'این کاربر هنوز از تو ربات وارد نشده.', show_alert=True); return
        target = pu['telegram_user_id']
        un = pu['username']
        urow = db.get_user(target)
        fn = urow.get('first_name') if urow else None
        if action == 'add_admin':
            db.add_group_admin(target, un, fn)
            bot.answer_callback_query(call.id, 'اضافه شد.')
            _edit_panel(cid, mid, _group_admins_text(), _group_admins_kb(), parse_mode='HTML'); return
        if action == 'add_bot_admin':
            db.add_bot_admin(target, un, fn)
            update_admin_status_msg(target)
            _set_admin_commands(target)
            bot.answer_callback_query(call.id, 'اضافه شد.')
            _edit_panel(cid, mid, _bot_admins_text(), _bot_admins_kb(), parse_mode='HTML'); return
        if action == 'add_vip':
            db.add_vip_user(target, un, fn)
            bot.answer_callback_query(call.id, 'اضافه شد.')
            _edit_panel(cid, mid, _vip_text(), _vip_twitter_kb(), parse_mode='HTML'); return
        if action == 'add_ig_vip':
            db.add_instagram_vip_user(target, un, fn)
            bot.answer_callback_query(call.id, 'اضافه شد.')
            _edit_panel(cid, mid, _instagram_vip_text(), _instagram_vip_kb(), parse_mode='HTML'); return
        bot.answer_callback_query(call.id); return

    if data == 'owner:add_admin':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        set_state(uid, cid, S_WAIT_ADMIN_ID, prompt_mid=mid)
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:group_admins'), _btn_home())
        _edit_panel(cid, mid, '👤 یوزرنیم پنلی کاربر مورد نظر را بنویسید (همون یوزرنیمی که موقع ساخت کاربر پنل تعیین شده):', kb); return

    if data.startswith('remove_admin:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        target = int(data.split(':')[1])
        db.remove_group_admin(target)
        _reset_user_commands(target)
        bot.answer_callback_query(call.id, 'حذف شد.')
        _edit_panel(cid, mid, '👥 ادمین حذف شد.', _group_admins_kb()); return

    if data == 'owner:bot_admins':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _bot_admins_text(), _bot_admins_kb()); return

    if data == 'bot_admin:add':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        set_state(uid, cid, S_WAIT_BOT_ADMIN_ID, prompt_mid=mid)
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:bot_admins'), _btn_home())
        _edit_panel(cid, mid, '👤 یوزرنیم پنلی کاربر مورد نظر را بنویسید (همون یوزرنیمی که موقع ساخت کاربر پنل تعیین شده):', kb); return

    if data == 'bot_admin:remove_list':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        bot.answer_callback_query(call.id)
        admins = db.get_all_bot_admins()
        if not admins: _edit_panel(cid, mid, '👤 هیچ ادمینی برای حذف وجود ندارد.', _bot_admins_kb()); return
        _edit_panel(cid, mid, '👤 کدام ادمین را حذف کنید؟', _bot_admins_remove_kb()); return

    if data.startswith('remove_bot_admin:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        target = int(data.split(':')[1])
        db.remove_bot_admin(target)
        _reset_user_commands(target)
        key = f'status_msg_{target}'
        mid_str = db.get_setting(key)
        if mid_str:
            try: bot.delete_message(target, int(mid_str)); db.set_setting(key, '')
            except Exception: pass
        bot.answer_callback_query(call.id, 'حذف شد.')
        _edit_panel(cid, mid, _bot_admins_text(), _bot_admins_kb()); return

    if data == 'owner:vip':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '👑 <b>VIP</b>\n\nلطفا بخش مورد نظر را انتخاب کنید:', _vip_kb()); return

    if data == 'owner:vip_twitter':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _vip_text(), _vip_twitter_kb(), parse_mode='HTML'); return

    if data == 'owner:vip_instagram':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _instagram_vip_text(), _instagram_vip_kb(), parse_mode='HTML'); return

    if data == 'vip:add':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        set_state(uid, cid, S_WAIT_VIP_ID, prompt_mid=mid)
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:vip_twitter'), _btn_home())
        _edit_panel(cid, mid, '👑 یوزرنیم پنلی کاربر مورد نظر را بنویسید (همون یوزرنیمی که موقع ساخت کاربر پنل تعیین شده):', kb); return

    if data == 'vip:remove_list':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        bot.answer_callback_query(call.id)
        vips = db.get_all_vip_users()
        if not vips: _edit_panel(cid, mid, '👑 هیچ VIP‌ای برای حذف وجود ندارد.', _vip_twitter_kb()); return
        _edit_panel(cid, mid, '👑 کدام VIP را حذف کنید؟', _vip_remove_kb()); return

    if data.startswith('remove_vip:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        db.remove_vip_user(int(data.split(':')[1]))
        bot.answer_callback_query(call.id, 'حذف شد.')
        _edit_panel(cid, mid, _vip_text(), _vip_twitter_kb(), parse_mode='HTML'); return

    if data == 'ig_vip:add':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        set_state(uid, cid, S_WAIT_INSTAGRAM_VIP_ID, prompt_mid=mid)
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:vip_instagram'), _btn_home())
        _edit_panel(cid, mid, '👑 یوزرنیم پنلی کاربر مورد نظر را بنویسید (همون یوزرنیمی که موقع ساخت کاربر پنل تعیین شده):', kb); return

    if data == 'ig_vip:remove_list':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        bot.answer_callback_query(call.id)
        vips = db.get_all_instagram_vip_users()
        if not vips: _edit_panel(cid, mid, '👑 هیچ VIP‌ای برای حذف وجود ندارد.', _instagram_vip_kb()); return
        _edit_panel(cid, mid, '👑 کدام VIP را حذف کنید؟', _instagram_vip_remove_kb()); return

    if data.startswith('remove_ig_vip:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        db.remove_instagram_vip_user(int(data.split(':')[1]))
        bot.answer_callback_query(call.id, 'حذف شد.')
        _edit_panel(cid, mid, _instagram_vip_text(), _instagram_vip_kb(), parse_mode='HTML'); return

    if data == 'owner:ht_access':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _hashtag_access_text(), _hashtag_toggle_kb(), parse_mode='HTML'); return

    if data.startswith('toggle_ht:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        hid = int(data.split(':')[1])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: bot.answer_callback_query(call.id, 'هشتگ یافت نشد.'); return
        if ht.get('is_active'):
            if len(db.get_active_hashtags()) <= 1:
                bot.answer_callback_query(call.id, '⚠️ نمی‌توان آخرین هشتگ فعال را غیرفعال کرد.', show_alert=True); return
            db.set_hashtag_active(hid, False)
            bot.answer_callback_query(call.id, f'❌ {ht["name"]} غیرفعال شد.')
        else:
            db.set_hashtag_active(hid, True)
            bot.answer_callback_query(call.id, f'✅ {ht["name"]} فعال شد.')
        try: bot.edit_message_text(_hashtag_access_text(), cid, mid, parse_mode='HTML', reply_markup=_hashtag_toggle_kb())
        except Exception: pass
        update_all_admin_status_messages(); return

    if data.startswith('user_ht_txt:'):
        parts = data.split(':')
        hid, count = int(parts[1]), int(parts[2])
        if not db.is_operation_active(): bot.answer_callback_query(call.id, 'عملیاتی در جریان نیست.', show_alert=True); return
        pu = _require_panel_login(uid, cid)
        if pu is None: bot.answer_callback_query(call.id); return
        ht = db.get_hashtag_by_id(hid)
        if not ht or not db.is_hashtag_visible_to_zone(hid, pu['zone_id']):
            bot.answer_callback_query(call.id, 'این هشتگ برای ناحیه‌ی شما نیست.', show_alert=True); return
        bot.answer_callback_query(call.id)
        try: bot.delete_message(cid, mid)
        except Exception: pass
        _deliver_texts_from_hashtag(uid, cid, count, hid, panel_user_id=pu.get('id')); return

    if data.startswith('user_ht_photo:'):
        hid = int(data.split(':')[1])
        if not db.is_operation_active(): bot.answer_callback_query(call.id, 'عملیاتی در جریان نیست.', show_alert=True); return
        pu = _require_panel_login(uid, cid)
        if pu is None: bot.answer_callback_query(call.id); return
        ht = db.get_hashtag_by_id(hid)
        if not ht or not db.is_hashtag_visible_to_zone(hid, pu['zone_id']):
            bot.answer_callback_query(call.id, 'این هشتگ برای ناحیه‌ی شما نیست.', show_alert=True); return
        bot.answer_callback_query(call.id)
        try: bot.delete_message(cid, mid)
        except Exception: pass
        _deliver_photos_batch(uid, cid, hid, panel_user_id=pu.get('id')); return

    if data.startswith('user_ht_reel:'):
        hid = int(data.split(':')[1])
        if not db.is_operation_active(): bot.answer_callback_query(call.id, 'عملیاتی در جریان نیست.', show_alert=True); return
        pu = _require_panel_login(uid, cid)
        if pu is None: bot.answer_callback_query(call.id); return
        ht = db.get_hashtag_by_id(hid)
        if not ht or not db.is_hashtag_visible_to_zone(hid, pu['zone_id']):
            bot.answer_callback_query(call.id, 'این هشتگ برای ناحیه‌ی شما نیست.', show_alert=True); return
        bot.answer_callback_query(call.id)
        try: bot.delete_message(cid, mid)
        except Exception: pass
        _deliver_reel(uid, cid, hid, zone_id=pu['zone_id'], panel_user_id=pu.get('id')); return

    if data.startswith('user_ht_story:'):
        hid = int(data.split(':')[1])
        if not db.is_operation_active(): bot.answer_callback_query(call.id, 'عملیاتی در جریان نیست.', show_alert=True); return
        pu = _require_panel_login(uid, cid)
        if pu is None: bot.answer_callback_query(call.id); return
        ht = db.get_hashtag_by_id(hid)
        if not ht or not db.is_hashtag_visible_to_zone(hid, pu['zone_id']):
            bot.answer_callback_query(call.id, 'این هشتگ برای ناحیه‌ی شما نیست.', show_alert=True); return
        bot.answer_callback_query(call.id)
        try: bot.delete_message(cid, mid)
        except Exception: pass
        _deliver_story(uid, cid, hid, zone_id=pu['zone_id'], panel_user_id=pu.get('id')); return

    if data == 'owner:msg_settings':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zones = db.get_all_zones()
        if not zones:
            bot.answer_callback_query(call.id, 'ابتدا حداقل یک ناحیه بسازید.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📁 پیام‌های کدام ناحیه را می‌خواهید ویرایش کنید؟', zone_pick_kb('msgzone', include_all=True)); return

    if data.startswith('msgzone:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        raw = data.split(':', 1)[1]
        if raw == 'all':
            set_admin_zone_ctx(uid, cid, None)
            bot.answer_callback_query(call.id)
            _edit_panel(cid, mid, _msg_settings_text('🌐 همگانی (پیش‌فرض همه‌ی ناحیه‌ها)'), _msg_settings_kb()); return
        zid  = int(raw)
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        set_admin_zone_ctx(uid, cid, zid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _msg_settings_text(zone['name']), _msg_settings_kb()); return

    if data.startswith('msg:preview:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        key = data.split(':', 2)[2]
        field = get_msg_field(key)
        if not field: bot.answer_callback_query(call.id); return
        zid = get_admin_zone_ctx(uid, cid)
        current = db.get_zone_setting(zid, field['key'], field['default'])
        bot.answer_callback_query(call.id)
        try:
            bot.send_message(cid, current or '(هنوز چیزی تنظیم نشده)', parse_mode='HTML')
        except Exception:
            # اگه فرمت HTML ذخیره‌شده به هر دلیلی نامعتبر بود، بدون فرمت بفرست
            bot.send_message(cid, current or '(هنوز چیزی تنظیم نشده)')
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton('✏️ تغییر بده', callback_data=f'msg:doedit:{key}'))
        kb.add(_btn_back('owner:msg_settings'), _btn_home())
        _edit_panel(cid, mid,
            f'📄 <b>{field["label"]}</b>\n\nپیام فعلی رو دقیقاً همون‌طوری که کاربر می‌بینه، بالا فرستادم 👆\n\nمی‌خوای تغییرش بدی؟',
            kb); return

    if data.startswith('msg:doedit:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        key = data.split(':', 2)[2]
        field = get_msg_field(key)
        if not field: bot.answer_callback_query(call.id); return
        set_state(uid, cid, field['state'], prompt_mid=mid)
        bot.answer_callback_query(call.id)
        hint = f'\n\n{field["hint"]}' if field['hint'] else ''
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:msg_settings'), _btn_home())
        _edit_panel(cid, mid, f'📝 پیام جدید برای «{field["label"]}» را بفرستید:{hint}', kb); return

    if data == 'msg:toggle_quick_access':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        db.set_quick_access_enabled(not db.is_quick_access_enabled())
        bot.answer_callback_query(call.id, 'انجام شد.')
        zid = get_admin_zone_ctx(uid, cid)
        zone_label = '🌐 همگانی (پیش‌فرض همه‌ی ناحیه‌ها)' if zid is None else (db.get_zone(zid) or {}).get('name')
        _edit_panel(cid, mid, _msg_settings_text(zone_label), _msg_settings_kb()); return

    if data == 'owner:website':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _website_text(), _website_kb()); return

    if data == 'website:toggle':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        current = db.get_website_status()
        db.set_website_status(not current)
        bot.answer_callback_query(call.id, f'وب سایت {"غیر فعال شد ❌" if current else "فعال شد ✅"}')
        _edit_panel(cid, mid, _website_text(), _website_kb()); return

    if data == 'website:change_url':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        set_state(uid, cid, S_WAIT_WEBSITE_URL)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '🔗 <b>تغییر لینک وب سایت</b>\n\nلینک جدید:', _website_change_url_kb()); return

    if data.startswith('del_ht:'):
        if not is_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        hid = int(data.split(':')[1])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: bot.answer_callback_query(call.id, 'هشتگ پیدا نشد.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, f'آیا مطمئنید هشتگ «{ht["name"]}» با تمام محتوایش حذف شود؟',
                    confirm_delete_hashtag_kb(hid)); return

    if data.startswith('confirm_del_ht:'):
        if not is_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        hid  = int(data.split(':')[1])
        ht   = db.get_hashtag_by_id(hid)
        name = ht['name'] if ht else str(hid)
        db.delete_hashtag(hid)
        update_all_admin_status_messages()
        _report_to_owner(f'هشتگ «{name}» حذف شد توسط {call.from_user.first_name}')
        bot.answer_callback_query(call.id, 'حذف شد.')
        try: bot.edit_message_text(f'✅ هشتگ «{name}» حذف شد.', cid, mid)
        except Exception: bot.send_message(cid, f'✅ هشتگ «{name}» حذف شد.')
        return

    if data == 'cancel_del_ht':
        bot.answer_callback_query(call.id, 'لغو شد.')
        try: bot.edit_message_text('❌ لغو شد.', cid, mid)
        except Exception: pass
        return

    if data.startswith('flood:forgive_ask:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        target = int(data.split(':')[2])
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton('✅ بله، مطمئنم', callback_data=f'flood:forgive_confirm:{target}'),
               InlineKeyboardButton('❌ نه', callback_data='flood:cancel'))
        try: bot.edit_message_text(f'مطمئنی می‌خوای کاربر {target} رو از مسدودی خارج کنی؟', cid, mid,
                                   reply_markup=kb)
        except Exception: pass
        return

    if data == 'flood:cancel':
        bot.answer_callback_query(call.id, 'لغو شد.')
        try: bot.edit_message_text('لغو شد.', cid, mid)
        except Exception: pass
        return

    if data.startswith('flood:forgive_confirm:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک.'); return
        target = int(data.split(':')[2])
        state  = db.get_flood_state(target)
        db.flood_forgive_permanent(target)
        bot.answer_callback_query(call.id, 'کاربر بخشیده شد.')
        try: bot.edit_message_text(f'✅ کاربر {target} از مسدودی خارج شد.', cid, mid)
        except Exception: pass
        if state and state.get('notice_chat_id') and state.get('notice_msg_id'):
            try:
                bot.edit_message_text('دوست عزیز ادمین شما را از مسدودی خارج کرد',
                                      state['notice_chat_id'], state['notice_msg_id'])
                def _del_later():
                    time.sleep(60)
                    try: bot.delete_message(state['notice_chat_id'], state['notice_msg_id'])
                    except Exception: pass
                threading.Thread(target=_del_later, daemon=True).start()
            except Exception:
                try: bot.send_message(target, 'دوست عزیز ادمین شما را از مسدودی خارج کرد')
                except Exception: pass
        return

    if data.startswith('sel_ht_text:'):
        if not is_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        hid = int(data.split(':')[1])
        ht  = db.get_hashtag_by_id(hid)
        if not ht: bot.answer_callback_query(call.id, 'هشتگ پیدا نشد.'); return
        set_state(uid, cid, S_WAIT_GROUP_CONTENT, hashtag_id=hid)
        bot.answer_callback_query(call.id)
        try: bot.edit_message_text(f'📍 هشتگ «{_html.escape(ht["name"])}» انتخاب شد.\nمتن یا عکس ارسال کنید.', cid, mid)
        except Exception: bot.send_message(cid, f'📍 هشتگ «{_html.escape(ht["name"])}» انتخاب شد.')
        return

    # ─────────────────────────────────────────────────────────────────
    # حساب کاربری (پنل ورود با یوزرنیم/پسورد) — فقط ورود، ثبت‌نام با ادمینه
    # ─────────────────────────────────────────────────────────────────
    if data == 'account:login':
        bot.answer_callback_query(call.id)
        set_state(uid, cid, S_WAIT_PU_LOGIN_USERNAME)
        _edit_panel(cid, mid, '🔓 یوزرنیم خود را وارد کنید:', InlineKeyboardMarkup()); return

    if data == 'account:logout':
        db.panel_logout(uid)
        bot.answer_callback_query(call.id, 'خارج شدید.')
        bot.send_message(cid, '🔐 خارج شدید. برای ادامه دوباره وارد شوید.', reply_markup=login_required_kb()); return

    # ─────────────────────────────────────────────────────────────────
    # افزودن کاربر پنل توسط ادمین
    # ─────────────────────────────────────────────────────────────────
    if data == 'admin_pu:add':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zones = db.get_all_zones()
        if not zones:
            bot.answer_callback_query(call.id, 'ابتدا حداقل یک ناحیه بسازید.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📁 این کاربر عضو کدام ناحیه باشد؟', zone_pick_kb()); return

    # ─────────────────────────────────────────────────────────────────
    # دسترسیِ سرویس (app/bot/site) - هم سطحِ ناحیه هم override شخصیِ کاربر
    # (فازِ ۸ - معادلِ باتیِ همون چیزی که تویِ اپ زیرِ هر کاربر/ناحیه هست)
    # ─────────────────────────────────────────────────────────────────
    if data.startswith('zone_services:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[1])
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        current = db.get_zone_allowed_services(zid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _zone_services_text(zone, current), zone_services_kb(zid, current), parse_mode='HTML'); return

    if data.startswith('zone_services_toggle:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        _, zid_s, key = data.split(':')
        zid = int(zid_s)
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        current = set(db.get_zone_allowed_services(zid))
        if key in current: current.discard(key)
        else: current.add(key)
        db.set_zone_allowed_services(zid, current)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _zone_services_text(zone, current), zone_services_kb(zid, current), parse_mode='HTML'); return

    if data.startswith('puser_services:'):
        pid = int(data.split(':')[1])
        pu = db.get_panel_user(pid)
        if not pu:
            bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        cmd = commander_pu(uid)
        is_cmd_path = bool(cmd) and db.commander_can_manage_zone(cmd['id'], pu['zone_id']) and db.commander_has_permission(cmd['id'], 'user.change_service_access')
        if not (is_bot_admin_or_owner(uid) or is_cmd_path):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        effective = db.get_user_allowed_services(pid)
        has_override = pu.get('allowed_services') is not None
        back_cb = f'cmd:puser:{pid}' if is_cmd_path and not is_bot_admin_or_owner(uid) else None
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _puser_services_text(pu, effective, has_override),
                    puser_services_kb(pid, effective, has_override, back_cb=back_cb), parse_mode='HTML'); return

    if data.startswith('puser_services_toggle:'):
        _, pid_s, key = data.split(':')
        pid = int(pid_s)
        pu = db.get_panel_user(pid)
        if not pu:
            bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        cmd = commander_pu(uid)
        is_cmd_path = bool(cmd) and db.commander_can_manage_zone(cmd['id'], pu['zone_id']) and db.commander_has_permission(cmd['id'], 'user.change_service_access')
        if not (is_bot_admin_or_owner(uid) or is_cmd_path):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        effective = set(db.get_user_allowed_services(pid))
        if key in effective: effective.discard(key)
        else: effective.add(key)
        db.set_user_allowed_services(pid, effective)
        pu = db.get_panel_user(pid)
        back_cb = f'cmd:puser:{pid}' if is_cmd_path and not is_bot_admin_or_owner(uid) else None
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _puser_services_text(pu, effective, True),
                    puser_services_kb(pid, effective, True, back_cb=back_cb), parse_mode='HTML'); return

    if data.startswith('puser_services_reset:'):
        pid = int(data.split(':')[1])
        pu = db.get_panel_user(pid)
        if not pu:
            bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        cmd = commander_pu(uid)
        is_cmd_path = bool(cmd) and db.commander_can_manage_zone(cmd['id'], pu['zone_id']) and db.commander_has_permission(cmd['id'], 'user.change_service_access')
        if not (is_bot_admin_or_owner(uid) or is_cmd_path):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        db.set_user_allowed_services(pid, None)
        effective = db.get_user_allowed_services(pid)
        back_cb = f'cmd:puser:{pid}' if is_cmd_path and not is_bot_admin_or_owner(uid) else None
        bot.answer_callback_query(call.id, 'به تنظیمِ ناحیه برگشت.')
        _edit_panel(cid, mid, _puser_services_text(pu, effective, False),
                    puser_services_kb(pid, effective, False, back_cb=back_cb), parse_mode='HTML'); return

    # ─────────────────────────────────────────────────────────────────
    # پنلِ فرمانده (فازِ ۸) - همون کاربرها/ناحیه‌ها ولی گیت‌شده با
    # COMMANDER_PERMISSIONS، نه owner/admin بودن.
    # ─────────────────────────────────────────────────────────────────
    if data == 'cmd:zones':
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _commander_zones_text(cmd), commander_zones_kb(cmd['id']), parse_mode='HTML'); return

    if data == 'cmd:zone_create':
        cmd = commander_pu(uid)
        if not cmd or not db.commander_has_permission(cmd['id'], 'zone.create'):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        set_state(uid, cid, S_WAIT_CMD_ZONE_NAME)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📝 نامِ ناحیه‌ی جدید را وارد کنید:', InlineKeyboardMarkup()); return

    if data.startswith('cmd:zone:'):
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        zid = int(data.split(':')[2])
        zone = db.get_zone(zid)
        if not zone or not db.commander_can_manage_zone(cmd['id'], zid):
            bot.answer_callback_query(call.id, 'به این ناحیه دسترسی ندارید.', show_alert=True); return
        perms = db.get_commander_permissions(cmd['id'])
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _commander_zone_detail_text(zone, cmd),
                    commander_zone_detail_kb(cmd['id'], zid, perms), parse_mode='HTML'); return

    if data.startswith('cmd:puser_add:'):
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        zid = int(data.split(':')[2])
        if not db.commander_can_manage_zone(cmd['id'], zid) or not db.commander_has_permission(cmd['id'], 'user.add'):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        if not db.commander_can_create_users(cmd['id']):
            bot.answer_callback_query(call.id, 'به سقفِ ساختِ کاربرِ خودتان رسیده‌اید.', show_alert=True); return
        set_state(uid, cid, S_WAIT_CMD_PU_USERNAME, zone_id=zid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '👤 یوزرنیمِ کاربرِ جدید را وارد کنید:', InlineKeyboardMarkup()); return

    if data.startswith('cmd:puser:'):
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        pid = int(data.split(':')[2])
        pu = db.get_panel_user(pid)
        if not pu or not db.commander_can_manage_zone(cmd['id'], pu['zone_id']):
            bot.answer_callback_query(call.id, 'به این کاربر دسترسی ندارید.', show_alert=True); return
        perms = db.get_commander_permissions(cmd['id'])
        zone = db.get_zone(pu['zone_id'])
        show_pw = 'user.view_credentials' in perms
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _commander_puser_detail_text(pu, zone['name'] if zone else '—', show_pw),
                    commander_puser_detail_kb(cmd['id'], pid, pu['zone_id'], perms), parse_mode='HTML'); return

    if data.startswith('cmd:puser_reset_pw:'):
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        pid = int(data.split(':')[2])
        pu = db.get_panel_user(pid)
        if not pu or not db.commander_can_manage_zone(cmd['id'], pu['zone_id']) or not db.commander_has_permission(cmd['id'], 'user.reset_password'):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        new_pw = db.reset_panel_user_password(pid)
        bot.answer_callback_query(call.id, 'پسورد ریست شد.')
        bot.send_message(cid, f'🔄 پسوردِ جدیدِ «{_html.escape(pu["username"])}»: <code>{_html.escape(new_pw)}</code>', parse_mode='HTML')
        return

    if data.startswith('cmd:puser_remove_confirm:'):
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        pid = int(data.split(':')[2])
        pu = db.get_panel_user(pid)
        if not pu or not db.commander_can_manage_zone(cmd['id'], pu['zone_id']) or not db.commander_has_permission(cmd['id'], 'user.remove'):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, f'⚠️ کاربرِ «{_html.escape(pu["username"])}» حذف شود؟',
                    commander_puser_remove_confirm_kb(pid, pu['zone_id']), parse_mode='HTML'); return

    if data.startswith('cmd:puser_remove:'):
        cmd = commander_pu(uid)
        if not cmd:
            bot.answer_callback_query(call.id, 'شما فرمانده نیستید.', show_alert=True); return
        pid = int(data.split(':')[2])
        pu = db.get_panel_user(pid)
        if not pu or not db.commander_can_manage_zone(cmd['id'], pu['zone_id']) or not db.commander_has_permission(cmd['id'], 'user.remove'):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = pu['zone_id']
        db.delete_panel_user(pid)
        perms = db.get_commander_permissions(cmd['id'])
        zone = db.get_zone(zid)
        bot.answer_callback_query(call.id, 'کاربر حذف شد.')
        if zone:
            _edit_panel(cid, mid, _commander_zone_detail_text(zone, cmd),
                        commander_zone_detail_kb(cmd['id'], zid, perms), parse_mode='HTML')
        return

    if data.startswith('admin_pu_zone_pick:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid  = int(data.split(':')[1])
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        set_state(uid, cid, S_WAIT_ADMIN_PU_USERNAME, zone_id=zid)
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, f'👤 یوزرنیم کاربر جدید (ناحیه «{_html.escape(zone["name"])}») را بنویسید:',
                    InlineKeyboardMarkup()); return

    # ─────────────────────────────────────────────────────────────────
    # ساختِ دسته‌ایِ N کاربرِ رندوم برایِ یک ناحیه (فازِ ۸ - معادلِ باتیِ
    # همون «ساختِ دسته‌ای» که تویِ اپ زیرِ هر ناحیه هست)
    # ─────────────────────────────────────────────────────────────────
    if data.startswith('zone_bulk_create:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid  = int(data.split(':')[1])
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        set_state(uid, cid, S_WAIT_ADMIN_BULK_COUNT, zone_id=zid)
        bot.answer_callback_query(call.id)
        _edit_panel(
            cid, mid,
            f'🔢 چند تا کاربرِ رندوم برایِ ناحیه‌ی «{_html.escape(zone["name"])}» ساخته بشه؟\n'
            f'یک عدد بین ۱ تا {_MAX_BULK_CREATE} بفرست:',
            InlineKeyboardMarkup(),
        ); return

    # ─────────────────────────────────────────────────────────────────
    # ایمپورتِ دسته‌ایِ کاربر از اکسل (فازِ ۴)
    # ─────────────────────────────────────────────────────────────────
    if data == 'admin_pu:import_xlsx':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        set_state(uid, cid, S_WAIT_ADMIN_XLSX_FILE)
        bot.answer_callback_query(call.id)
        _edit_panel(
            cid, mid,
            '📊 فایلِ اکسل (.xlsx) رو بفرست - ستونِ اول یوزرنیم، ستونِ دوم پسورد.\n'
            'ردیفِ اول می‌تونه هدر باشه (مثلاً «یوزرنیم»/«پسورد») یا مستقیم داده.',
            InlineKeyboardMarkup(),
        ); return

    if data.startswith('admin_xlsx_zone_pick:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        if cur_state(uid, cid) != S_WAIT_ADMIN_XLSX_ZONE_PICK:
            bot.answer_callback_query(call.id, 'این درخواست منقضی شده. دوباره از اول امتحان کن.', show_alert=True)
            return
        zid  = int(data.split(':')[1])
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        pairs = state_data(uid, cid).get('pairs') or []
        clear_state(uid, cid)
        bot.answer_callback_query(call.id)
        if not pairs:
            _edit_panel(cid, mid, '⚠️ چیزی برای ساختن نمونده (شاید state منقضی شده). دوباره از اول امتحان کن.',
                        InlineKeyboardMarkup())
            return
        result = db.bulk_import_panel_users(zid, pairs, created_by=None)
        created, skipped = result['created'], result['skipped']
        lines = [f'✅ {len(created)} کاربر تو ناحیه‌ی «{_html.escape(zone["name"])}» ساخته شد.']
        if skipped:
            lines.append(f'⚠️ {len(skipped)} ردیف رد شد:')
            # حداکثر ۱۵ تا دلیل نشون بده که پیام خیلی طولانی نشه
            for s in skipped[:15]:
                lines.append(f'  • {_html.escape(str(s["username"]))} — {_html.escape(s["reason"])}')
            if len(skipped) > 15:
                lines.append(f'  … و {len(skipped) - 15} موردِ دیگر.')
        _edit_panel(cid, mid, '\n'.join(lines), InlineKeyboardMarkup()); return

    # ─────────────────────────────────────────────────────────────────
    # اکسپورتِ اکسل (فازِ ۸ - معادلِ باتیِ همون چیزی که تویِ اپ زیرِ
    # پنلِ کاربران هست: همه / یک ناحیه / چند ناحیه‌ی دلخواه)
    # ─────────────────────────────────────────────────────────────────
    if data == 'owner:export_menu':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📤 <b>اکسپورتِ اکسل</b>\n\nچی می‌خوای اکسپورت بشه؟', export_menu_kb(), parse_mode='HTML'); return

    if data == 'export:all':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id, 'در حال آماده‌سازی...')
        xlsx = excel_tools.build_users_xlsx(db.get_export_rows(), include_password=True)
        bot.send_document(cid, InputFile(_io.BytesIO(xlsx), filename='users_all.xlsx')); return

    if data.startswith('export:zone:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        zone = db.get_zone(zid)
        if not zone:
            bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        bot.answer_callback_query(call.id, 'در حال آماده‌سازی...')
        xlsx = excel_tools.build_users_xlsx(db.get_export_rows(zone_id=zid), include_password=True)
        bot.send_document(cid, InputFile(_io.BytesIO(xlsx), filename=f'users_{zone["name"]}.xlsx')); return

    if data == 'export:pick_zones':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        init_export_selection(uid, cid, [])
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📤 ناحیه‌هایی که می‌خوای اکسپورت بشن رو انتخاب کن:', export_zone_select_kb([])); return

    if data.startswith('export:toggle:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        sel = toggle_export_zone(uid, cid, zid)
        if sel is None:
            bot.answer_callback_query(call.id, 'دوباره از منو شروع کن.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📤 ناحیه‌هایی که می‌خوای اکسپورت بشن رو انتخاب کن:', export_zone_select_kb(sel)); return

    if data == 'export:toggle_all':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        all_ids = [z['id'] for z in db.get_all_zones()]
        cur = get_export_selection(uid, cid) or set()
        sel = set_export_zones_all(uid, cid, all_ids, select=len(cur) < len(all_ids))
        if sel is None:
            bot.answer_callback_query(call.id, 'دوباره از منو شروع کن.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, '📤 ناحیه‌هایی که می‌خوای اکسپورت بشن رو انتخاب کن:', export_zone_select_kb(sel)); return

    if data == 'export:confirm':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        sel = get_export_selection(uid, cid)
        if not sel:
            bot.answer_callback_query(call.id, 'حداقل یک ناحیه انتخاب کن.', show_alert=True); return
        clear_export_selection(uid, cid)
        ids = sorted(sel)
        names = '_'.join(z['name'] for z in (db.get_zone(z) for z in ids) if z)
        bot.answer_callback_query(call.id, 'در حال آماده‌سازی...')
        xlsx = excel_tools.build_users_xlsx(db.get_export_rows(zone_ids=ids), include_password=True)
        bot.send_document(cid, InputFile(_io.BytesIO(xlsx), filename=f'users_{names or "selected"}.xlsx')); return

    # ─────────────────────────────────────────────────────────────────
    # مدیریت ناحیه‌ها و کاربران پنل (ادمین)
    # ─────────────────────────────────────────────────────────────────
    if data == 'owner:zones':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _zones_admin_text(), owner_zones_kb()); return

    if data == 'zone:add':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        set_state(uid, cid, S_WAIT_ZONE_NAME, prompt_mid=mid)
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:zones'), _btn_home())
        _edit_panel(cid, mid, '📁 نام ناحیه‌ی جدید را بنویسید:', kb); return

    if data.startswith('zone:open:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        zone = db.get_zone(zid)
        if not zone: bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); _edit_panel(cid, mid, _zones_admin_text(), owner_zones_kb()); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _zone_detail_text(zone), zone_detail_kb(zid)); return

    if data == 'owner:toggle_guest_login':
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        if not db.is_guest_login_enabled() and not db.get_guest_zone_id():
            bot.answer_callback_query(call.id, 'اول باید یه ناحیه رو به‌عنوان «ناحیه‌ی مهمان‌ها» تنظیم کنی (وارد یه ناحیه شو).', show_alert=True)
            return
        db.set_guest_login_enabled(not db.is_guest_login_enabled())
        bot.answer_callback_query(call.id, 'انجام شد.')
        _edit_panel(cid, mid, _zones_admin_text(), owner_zones_kb(), parse_mode='HTML'); return

    if data.startswith('zone:set_guest:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        zone = db.get_zone(zid)
        if not zone: bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        db.set_guest_zone_id(zid)
        bot.answer_callback_query(call.id, 'این ناحیه، ناحیه‌ی مهمان‌ها شد.')
        _edit_panel(cid, mid, _zone_detail_text(zone), zone_detail_kb(zid), parse_mode='HTML'); return

    if data.startswith('zone:unset_guest:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        zone = db.get_zone(zid)
        db.set_guest_zone_id(None)
        db.set_guest_login_enabled(False)
        bot.answer_callback_query(call.id, 'لغو شد (ورود مهمان هم غیرفعال شد).')
        if zone:
            _edit_panel(cid, mid, _zone_detail_text(zone), zone_detail_kb(zid), parse_mode='HTML')
        return

    if data.startswith('zone:delete_confirm:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        zone = db.get_zone(zid)
        if not zone: bot.answer_callback_query(call.id, 'این ناحیه دیگر وجود ندارد.', show_alert=True); return
        bot.answer_callback_query(call.id)
        cnt = db.count_zone_users(zid)
        warn = f'\n\n⚠️ {cnt} کاربر این ناحیه هم حذف می‌شوند.' if cnt else ''
        _edit_panel(cid, mid, f'ناحیه‌ی «{_html.escape(zone["name"])}» حذف شود؟{warn}', zone_delete_confirm_kb(zid)); return

    if data.startswith('zone:delete_do:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zid = int(data.split(':')[2])
        db.delete_zone(zid)
        bot.answer_callback_query(call.id, 'حذف شد.')
        _edit_panel(cid, mid, _zones_admin_text(), owner_zones_kb()); return

    if data.startswith('puser:open:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        pu_id = int(data.split(':')[2])
        pu = db.get_panel_user(pu_id)
        if not pu: bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        zone = db.get_zone(pu['zone_id'])
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _panel_user_detail_text(pu, zone['name'] if zone else 'نامشخص', show_password=is_owner(uid)),
                    panel_user_detail_kb(pu_id, pu['zone_id'], can_see_password=is_owner(uid))); return

    if data.startswith('puser:reset_pw:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات می‌تواند پسورد را ریست/ببیند.'); return
        pu_id = int(data.split(':')[2])
        pu = db.get_panel_user(pu_id)
        if not pu: bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        new_pw = db.reset_panel_user_password(pu_id)
        bot.answer_callback_query(call.id, 'پسورد ریست شد.')
        zone = db.get_zone(pu['zone_id'])
        bot.send_message(cid,
            f'🔑 پسورد جدید برای «{_html.escape(pu["username"])}»:\n<code>{_html.escape(new_pw)}</code>\n\n'
            'این پسورد فقط همین یک‌بار نمایش داده می‌شود، آن را برای کاربر ارسال کنید.',
            parse_mode='HTML')
        _edit_panel(cid, mid, _panel_user_detail_text(db.get_panel_user(pu_id), zone['name'] if zone else 'نامشخص', show_password=True),
                    panel_user_detail_kb(pu_id, pu['zone_id'], can_see_password=True)); return

    if data.startswith('puser:delete_confirm:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        pu_id = int(data.split(':')[2])
        pu = db.get_panel_user(pu_id)
        if not pu: bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, f'کاربر «{_html.escape(pu["username"])}» حذف شود؟', panel_user_delete_confirm_kb(pu_id, pu['zone_id'])); return

    if data.startswith('puser:delete_do:'):
        if not is_bot_admin_or_owner(uid): bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        pu_id = int(data.split(':')[2])
        pu = db.get_panel_user(pu_id)
        zid = pu['zone_id'] if pu else None
        db.delete_panel_user(pu_id)
        bot.answer_callback_query(call.id, 'حذف شد.')
        if zid:
            zone = db.get_zone(zid)
            if zone:
                _edit_panel(cid, mid, _zone_detail_text(zone), zone_detail_kb(zid)); return
        _edit_panel(cid, mid, _zones_admin_text(), owner_zones_kb()); return

    # ─────────────────────────────────────────────────────────────────
    # افراد (سرپرست‌ها) — فقط مالک ربات مدیریت می‌کنه
    # ─────────────────────────────────────────────────────────────────
    if data == 'owner:people':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _people_list_text(), people_list_kb(), parse_mode='HTML'); return

    if data == 'people:add':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        set_state(uid, cid, S_WAIT_PEOPLE_USERNAME, prompt_mid=mid)
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(_btn_back('owner:people'), _btn_home())
        _edit_panel(cid, mid, '👤 یوزرنیم پنلی همون کاربری که می‌خوای سرپرست بشه رو بنویس:', kb); return

    if data.startswith('people:edit:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        pu_id = int(data.split(':')[2])
        pu = db.get_panel_user(pu_id)
        if not pu: bot.answer_callback_query(call.id, 'این کاربر دیگر وجود ندارد.', show_alert=True); return
        set_people_selection(uid, cid, pu_id, db.get_supervisor_zone_ids(pu_id))
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _people_zone_select_text(pu['username']),
                    people_zone_select_kb(db.get_supervisor_zone_ids(pu_id), pu_id), parse_mode='HTML'); return

    if data.startswith('people:toggle:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        zid = int(data.split(':')[2])
        sel = toggle_people_zone(uid, cid, zid)
        if not sel: bot.answer_callback_query(call.id, 'این عملیات منقضی شده، دوباره شروع کن.', show_alert=True); return
        pu = db.get_panel_user(sel['pu_id'])
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _people_zone_select_text(pu['username'] if pu else '؟'),
                    people_zone_select_kb(sel['zone_ids'], sel['pu_id']), parse_mode='HTML'); return

    if data == 'people:toggle_all':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        sel = get_people_selection(uid, cid)
        if not sel: bot.answer_callback_query(call.id, 'این عملیات منقضی شده، دوباره شروع کن.', show_alert=True); return
        all_zones = [z['id'] for z in db.get_all_zones()]
        select_all = len(sel['zone_ids']) < len(all_zones)
        sel = set_people_zones_all(uid, cid, all_zones, select_all)
        pu = db.get_panel_user(sel['pu_id'])
        bot.answer_callback_query(call.id)
        _edit_panel(cid, mid, _people_zone_select_text(pu['username'] if pu else '؟'),
                    people_zone_select_kb(sel['zone_ids'], sel['pu_id']), parse_mode='HTML'); return

    if data == 'people:confirm':
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        sel = get_people_selection(uid, cid)
        if not sel: bot.answer_callback_query(call.id, 'این عملیات منقضی شده، دوباره شروع کن.', show_alert=True); return
        db.set_supervisor_zones(sel['pu_id'], list(sel['zone_ids']))
        clear_people_selection(uid, cid)
        bot.answer_callback_query(call.id, 'ذخیره شد.')
        _edit_panel(cid, mid, _people_list_text(), people_list_kb(), parse_mode='HTML'); return

    if data.startswith('people:remove:'):
        if not is_owner(uid): bot.answer_callback_query(call.id, 'فقط مالک ربات.'); return
        pu_id = int(data.split(':')[2])
        db.remove_supervisor(pu_id)
        clear_people_selection(uid, cid)
        bot.answer_callback_query(call.id, 'نقش سرپرستی حذف شد.')
        _edit_panel(cid, mid, _people_list_text(), people_list_kb(), parse_mode='HTML'); return

    # ─────────────────────────────────────────────────────────────────
    # دیدن رمزها توسط خودِ سرپرست (هر panel_user که سرپرست حداقل یک ناحیه‌ست)
    # ─────────────────────────────────────────────────────────────────
    if data == 'super:zones':
        pu = db.get_panel_user_by_telegram_id(uid)
        if not pu or not db.is_supervisor(pu['id']):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        bot.answer_callback_query(call.id)
        bot.send_message(cid, '📁 ناحیه‌هایی که سرپرستشون هستی:', reply_markup=supervisor_zones_kb(pu['id'])); return

    if data.startswith('super:zone:'):
        pu = db.get_panel_user_by_telegram_id(uid)
        zid = int(data.split(':')[2])
        if not pu or zid not in db.get_supervisor_zone_ids(pu['id']):
            bot.answer_callback_query(call.id, 'دسترسی ندارید.'); return
        zone = db.get_zone(zid)
        users = [u for u in db.get_supervised_panel_users(pu['id']) if u['zone_id'] == zid]
        bot.answer_callback_query(call.id)
        bot.send_message(cid, _supervised_users_text(zone['name'] if zone else '؟', users), parse_mode='HTML'); return

    bot.answer_callback_query(call.id)

# ─────────────────────────────────────────────────────────────────────────────
# Group panel callback handler
# ─────────────────────────────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def catch_all(message):
    log.debug('Unhandled: user=%s chat=%s type=%s',
              message.from_user.id if message.from_user else '?',
              message.chat.id, message.content_type)

# ─────────────────────────────────────────────────────────────────────────────
# Background jobs
# ─────────────────────────────────────────────────────────────────────────────
