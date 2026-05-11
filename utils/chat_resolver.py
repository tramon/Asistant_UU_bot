import logging

from config import CHATS

logger = logging.getLogger(__name__)


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
