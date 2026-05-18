import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_CHAT_IDS, OWNER_USER_TELEGRAM_IDS

logger = logging.getLogger(__name__)


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


def private_chat_only(func):
    """Ігнорує команду якщо вона викликана не в особистому чаті."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        if update.effective_chat.type != "private":
            logger.warning(f"Команда викликана не в особистому чаті (chat_id={update.effective_chat.id}) — ігнорується")
            return
        return await func(update, context)

    return wrapper


def allowed_users_only(func):
    """Дозволяє виконання лише користувачам зі списку OWNER_USER_TELEGRAM_IDS."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        user_id = update.effective_user.id
        if user_id not in OWNER_USER_TELEGRAM_IDS:
            logger.warning(f"Доступ до команди заборонено для user_id={user_id}")
            await update.message.reply_text("⛔ У вас немає доступу до цієї команди.")
            return
        return await func(update, context)

    return wrapper
