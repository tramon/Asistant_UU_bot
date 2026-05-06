import asyncio
import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from announcements import ANNOUNCEMENTS
from config import BOT_TOKEN, CHATS, ALLOWED_CHAT_IDS

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
            for chat_id in ids:
                try:
                    await bot.send_message(chat_id=chat_id, text=t)
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
    text = CHATS[chat_key].get("info", "ℹ️ Немає інформації для цієї групи.")
    await update.message.reply_text(text)


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
