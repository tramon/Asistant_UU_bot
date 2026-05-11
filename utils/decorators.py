import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_CHAT_IDS

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
