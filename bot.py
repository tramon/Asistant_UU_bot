import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Декоратор фільтрації чатів ---

def allowed_chats_only(func):
    """Ігнорує всі запити з чатів не зі списку ALLOWED_CHAT_IDS."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    )
    await update.message.reply_text(text)


@allowed_chats_only
async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Корисна команда для отримання chat_id групи."""
    chat = update.effective_chat
    await update.message.reply_text(
        f"Chat ID: `{chat.id}`\nНазва: {chat.title or chat.first_name}",
        parse_mode="Markdown"
    )


@allowed_chats_only
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Невідома команда. Спробуй /help")


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Бот запущено. Polling...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()  # чекаємо поки не зупинять


if __name__ == "__main__":
    asyncio.run(main())