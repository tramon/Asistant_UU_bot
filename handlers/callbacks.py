import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CHATS, get_schedule_url
from utils.chat_resolver import get_chat_key_by_id
from utils.utils import get_study_week

logger = logging.getLogger(__name__)


async def week_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопки 'Який зараз тиждень?'"""
    query = update.callback_query
    await query.answer()
    chat_key = get_chat_key_by_id(query.message.chat.id)
    info_text = CHATS[chat_key].get("info", "") if chat_key else ""
    week = get_study_week()
    keyboard = [[InlineKeyboardButton("📅 Який зараз тиждень?", callback_data="week")]]
    await query.edit_message_text(
        text=f"{info_text}\n\n📅 Зараз {week} тиждень навчання.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопки 'Розклад'."""
    query = update.callback_query
    await query.answer()
    chat_key = get_chat_key_by_id(query.message.chat.id)
    if chat_key is None:
        await query.answer("ℹ️ Ця група не налаштована.", show_alert=True)
        return
    url = get_schedule_url(chat_key)
    if url is None:
        await query.answer("❌ Розклад не знайдено.", show_alert=True)
        return
    text = f"📅 Розклад:\n{chat_key}\n{url}"
    await query.message.reply_text(text, disable_web_page_preview=True)
