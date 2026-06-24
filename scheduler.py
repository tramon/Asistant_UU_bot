import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from announcements import ANNOUNCEMENTS
from config import CHATS, USER_STATUS_BLOCKED, get_active_users, update_user_status
from utils.chat_resolver import get_chat_ids

logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone("Europe/Kyiv")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    # misfire_grace_time=600 — якщо задача пропущена менш ніж 10 хв тому
    # (наприклад під час перезапуску між сесіями GitHub Actions) — відправити одразу.
    # Якщо більше 10 хв — пропустити, щоб не надсилати застарілі повідомлення.
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ, misfire_grace_time=600)

    for ann in ANNOUNCEMENTS:
        text = ann["text"]
        chat_ids = get_chat_ids(ann["chats"])
        trigger = CronTrigger.from_crontab(ann["cron"], timezone=KYIV_TZ)

        user_keys = ann.get("users", [])

        async def send_announcement(t=text, ids=chat_ids, keys=ann["chats"], ukeys=user_keys):
            # Якщо text — функція (lambda), викликаємо її в момент надсилання
            message = t() if callable(t) else t

            # --- Надсилання в групові чати ---
            for chat_id, chat_key in zip(ids, keys if keys != ["all"] else list(CHATS.keys())):
                try:
                    await bot.send_message(chat_id=chat_id, text=message)
                    logger.info(
                        f"Оголошення надіслано | чат: '{chat_key}' (id={chat_id}) | текст: '{message}'"
                    )
                except Exception as e:
                    logger.error(
                        f"Помилка надсилання | чат: '{chat_key}' (id={chat_id}) | {e}"
                    )

            # --- Надсилання особистих повідомлень ---
            if ukeys:
                active_users = get_active_users()
                for user in active_users:
                    user_id = user["user_id"]
                    username = user["username"]
                    try:
                        await bot.send_message(chat_id=user_id, text=message)
                        logger.info(
                            f"Особисте повідомлення надіслано | @{username} (id={user_id}) | текст: '{message}'"
                        )
                    except Exception as e:
                        if "Forbidden" in str(e):
                            logger.warning(f"@{username} (id={user_id}) заблокував бота → оновлюємо статус")
                            update_user_status(user_id, USER_STATUS_BLOCKED)
                        else:
                            logger.error(f"Помилка надсилання | @{username} (id={user_id}) | {e}")

        scheduler.add_job(send_announcement, trigger=trigger)
        logger.info(f"Заплановано: [{ann['cron']}] → чати: {ann['chats']}, користувачі: {user_keys}")

    return scheduler
