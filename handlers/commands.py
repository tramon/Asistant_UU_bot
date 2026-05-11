import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CHATS, get_schedule_url
from utils.decorators import allowed_chats_only
from utils.chat_resolver import get_chat_key_by_id
from utils.utils import get_study_week

logger = logging.getLogger(__name__)


@allowed_chats_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот активний ✅")


@allowed_chats_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Доступні команди:\n"
        "/start — перевірити що бот живий\n"
        "/help — список команд\n"
        "/chatid — показати ID цього чату\n"
        "/info — інформація про цю групу\n"
        "/week — який зараз тиждень навчання\n"
        "/schedule — розклад групи\n"
    )
    await update.message.reply_text(text)


@allowed_chats_only
async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(
        f"Chat ID: `{chat.id}`\nНазва: {chat.title or chat.first_name}",
        parse_mode="Markdown"
    )


@allowed_chats_only
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає інформацію специфічну для групи."""
    chat_key = get_chat_key_by_id(update.effective_chat.id)
    if chat_key is None:
        await update.message.reply_text("ℹ️ Ця група не налаштована.")
        return
    text = CHATS[chat_key].get("info", "ℹ️ Немає інформації для цієї групи.")
    keyboard = [
        [InlineKeyboardButton("📅 Який зараз тиждень?", callback_data="week")],
        [InlineKeyboardButton("📋 Розклад", callback_data="schedule")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


@allowed_chats_only
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає інформацію про поточний тиждень навчання."""
    current_week = get_study_week()
    await update.message.reply_text(f"📅 Зараз {current_week} тиждень навчання.")


@allowed_chats_only
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає посилання на розклад групи."""
    chat_key = get_chat_key_by_id(update.effective_chat.id)
    if chat_key is None:
        await update.message.reply_text("ℹ️ Ця група не налаштована.")
        return
    url = get_schedule_url(chat_key)
    if url is None:
        await update.message.reply_text("❌ Розклад для цієї групи не знайдено.")
        return
    text = f"📅 Розклад:\n{chat_key}\n{url}"
    await update.message.reply_text(text, disable_web_page_preview=True)


@allowed_chats_only
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Невідома команда. Спробуй /help")
