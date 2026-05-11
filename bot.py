import asyncio
import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

from announcements import ANNOUNCEMENTS
from utils.utils import get_study_week
from config import BOT_TOKEN, CHATS, ALLOWED_CHAT_IDS, get_schedule_url

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone("Europe/Kyiv")


# --- Хелпери ---

def get_chat_key_by_id(telegram_id: int) -> str | None:
    """Повертає ключ групи ('main', 'dev' тощо) за telegram_id."""
    for key, data in CHATS.items():
        if data["telegram_id"] == telegram_id:
            return key
    return None


def get_chat_ids(chat_keys: list[str]) -> list[int]:
    """Повертає список telegram_id за ключами з CHATS."""
    if chat_keys == ["all"]:
        return [v["telegram_id"] for v in CHATS.values()]
    result = []
    for key in chat_keys:
        if key in CHATS:
            result.append(CHATS[key]["telegram_id"])
        else:
            logger.warning(f"Чат '{key}' не знайдено в CHATS")
    return result


# --- Планувальник оголошень ---

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ)

    for ann in ANNOUNCEMENTS:
        text = ann["text"]
        chat_ids = get_chat_ids(ann["chats"])
        trigger = CronTrigger.from_crontab(ann["cron"], timezone=KYIV_TZ)

        async def send_announcement(t=text, ids=chat_ids):
            # Якщо text — функція (lambda), викликаємо її в момент надсилання
            message = t() if callable(t) else t
            for chat_id in ids:
                try:
                    await bot.send_message(chat_id=chat_id, text=message)
                    logger.info(f"Оголошення надіслано в {chat_id}")
                except Exception as e:
                    logger.error(f"Помилка надсилання в {chat_id}: {e}")

        scheduler.add_job(send_announcement, trigger=trigger)
        logger.info(f"Заплановано: [{ann['cron']}] → {ann['chats']}")

    return scheduler


# --- Декоратор фільтрації чатів ---

def allowed_chats_only(func):
    """Ігнорує запити з чатів не зі списку, або без повідомлення."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        chat_id = update.effective_chat.id
        if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
            logger.warning(f"Заблоковано запит з чату {chat_id}")
            return
        return await func(update, context)

    return wrapper


# --- Команди ---

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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def week_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопки 'Який зараз тиждень?'"""
    query = update.callback_query
    await query.answer()
    # Беремо оригінальний текст з CHATS, а не з поточного повідомлення
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
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає інформацію про поточний тиждень навчання."""
    current_week = get_study_week()
    await update.message.reply_text(f"📅 Зараз {current_week} тиждень навчання.")


@allowed_chats_only
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Невідома команда. Спробуй /help")


# --- Запуск ---

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CallbackQueryHandler(week_callback, pattern="^week$"))
    app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^schedule$"))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    scheduler = setup_scheduler(app.bot)
    scheduler.start()
    logger.info("Планувальник запущено")

    logger.info("Бот запущено. Polling...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())