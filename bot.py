import asyncio
import logging

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import BOT_TOKEN
from handlers.callbacks import week_callback, schedule_callback
from handlers.commands import start, help_command, chatid, info, week, schedule, unknown
from scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


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
