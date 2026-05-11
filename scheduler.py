import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from announcements import ANNOUNCEMENTS
from utils.chat_resolver import get_chat_ids

logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone("Europe/Kyiv")


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
