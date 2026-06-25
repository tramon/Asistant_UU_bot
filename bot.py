import asyncio
import logging

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import BOT_TOKEN
from handlers.callbacks import week_callback, schedule_callback
from handlers.commands import start, help_command, chatid, info, week, schedule, doc, reload_scheduler, unknown
from scheduler import setup_scheduler

class _FilterGetUpdates(logging.Filter):
    def __init__(self):
        super().__init__()
        self._first_seen = False

    def filter(self, record: logging.LogRecord) -> bool:
        if "getUpdates" not in record.getMessage():
            return True
        if not self._first_seen:
            self._first_seen = True
            return True  # first getUpdates — we do send
        return False     # others we filter for the sake of removing redundant logs.


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").addFilter(_FilterGetUpdates()) # here we filters 2-nd and all following getUpdate logs.
logger = logging.getLogger(__name__)


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("doc", doc))
    app.add_handler(CommandHandler("reload", reload_scheduler))
    app.add_handler(CallbackQueryHandler(week_callback, pattern="^week$"))
    app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^schedule$"))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    scheduler = setup_scheduler(app.bot)
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info("Планувальник запущено")

    logger.info("Бот запущено. Polling...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
