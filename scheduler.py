import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from announcements import ANNOUNCEMENTS
from config import CHATS, USER_STATUS_BLOCKED, get_active_users, load_announcements_from_sheet, update_user_status
from utils.chat_resolver import get_chat_ids

logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone("Europe/Kyiv")


async def send_announcement(bot: Bot, text, chat_ids: list, chat_keys: list, user_keys: list) -> None:
    """
    Надсилає одне оголошення в групові чати та/або особисті повідомлення.
    Винесено окремо для тестування.
    """
    message = text() if callable(text) else text

    # --- Надсилання в групові чати ---
    keys_iter = chat_keys if chat_keys != ["all"] else list(CHATS.keys())
    for chat_id, chat_key in zip(chat_ids, keys_iter):
        try:
            await bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"Оголошення надіслано | чат: '{chat_key}' (id={chat_id}) | текст: '{message}'")
        except Exception as e:
            logger.error(f"Помилка надсилання | чат: '{chat_key}' (id={chat_id}) | {e}")

    # --- Надсилання особистих повідомлень ---
    if user_keys:
        active_users = get_active_users()
        # ["all"] — всі активні; інакше — фільтр по username (з @ або без)
        if user_keys != ["all"]:
            normalized = [u.lstrip("@").lower() for u in user_keys]
            active_users = [u for u in active_users if u["username"].lower() in normalized]
        for user in active_users:
            user_id = user["user_id"]
            username = user["username"]
            try:
                await bot.send_message(chat_id=user_id, text=message)
                logger.info(f"Особисте повідомлення надіслано | @{username} (id={user_id}) | текст: '{message}'")
            except Exception as e:
                if "Forbidden" in str(e):
                    logger.warning(f"@{username} (id={user_id}) заблокував бота -> оновлюємо статус")
                    update_user_status(user_id, USER_STATUS_BLOCKED)
                else:
                    logger.error(f"Помилка надсилання | @{username} (id={user_id}) | {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    # misfire_grace_time=600 — якщо задача пропущена менш ніж 10 хв тому
    # (наприклад під час перезапуску між сесіями GitHub Actions) — відправити одразу.
    # Якщо більше 10 хв — пропустити, щоб не надсилати застарілі повідомлення.
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ, misfire_grace_time=600)

    # Спочатку пробуємо завантажити з Google Sheet, fallback на announcements.py
    sheet_announcements = load_announcements_from_sheet()
    if sheet_announcements is not None:
        announcements = sheet_announcements
        logger.info("Оголошення завантажено з Google Sheet")
    else:
        announcements = ANNOUNCEMENTS
        logger.warning("Не вдалось завантажити з Sheet — використовуємо announcements.py")

    for ann in announcements:
        text = ann["text"]
        chat_ids = get_chat_ids(ann["chats"])
        trigger = CronTrigger.from_crontab(ann["cron"], timezone=KYIV_TZ)
        user_keys = ann.get("users", [])

        async def job(t=text, ids=chat_ids, keys=ann["chats"], ukeys=user_keys):
            await send_announcement(bot, t, ids, keys, ukeys)

        scheduler.add_job(job, trigger=trigger)
        logger.info(f"Заплановано: [{ann['cron']}] -> чати: {ann['chats']}, користувачі: {user_keys}")

    return scheduler
