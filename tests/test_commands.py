"""
Тести команд бота.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_update(user_id: int, chat_type: str = "private"):
    """Будує мок Update з заданим user_id і типом чату."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.type = chat_type
    update.effective_chat.id = user_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def make_context(bot_data: dict = None):
    """Будує мок context з bot_data."""
    context = MagicMock()
    context.bot_data = bot_data or {}
    context.bot = MagicMock()
    return context


# --- Тести /reload ---

async def test_owner_can_reload_scheduler():
    """Власник може перезапустити планувальник."""
    from handlers.commands import reload_scheduler

    owner_id = 999
    old_scheduler = MagicMock()
    old_scheduler.running = True
    new_scheduler = MagicMock()

    update = make_update(user_id=owner_id)
    context = make_context(bot_data={"scheduler": old_scheduler})

    with patch("utils.decorators.OWNER_USER_TELEGRAM_IDS", [owner_id]), \
         patch("handlers.commands.setup_scheduler", return_value=new_scheduler):
        await reload_scheduler(update, context)

    old_scheduler.shutdown.assert_called_once_with(wait=False)
    new_scheduler.start.assert_called_once()
    assert context.bot_data["scheduler"] is new_scheduler
    update.message.reply_text.assert_called_once_with("✅ Планувальник перезапущено")


async def test_non_owner_cannot_reload_scheduler():
    """Не-власник отримує відмову і планувальник не перезапускається."""
    from handlers.commands import reload_scheduler

    owner_id = 999
    stranger_id = 111
    old_scheduler = MagicMock()
    old_scheduler.running = True

    update = make_update(user_id=stranger_id)
    context = make_context(bot_data={"scheduler": old_scheduler})

    with patch("utils.decorators.OWNER_USER_TELEGRAM_IDS", [owner_id]), \
         patch("handlers.commands.setup_scheduler") as mock_setup:
        await reload_scheduler(update, context)

    old_scheduler.shutdown.assert_not_called()
    mock_setup.assert_not_called()
    update.message.reply_text.assert_called_once_with("⛔ У вас немає доступу до цієї команди.")


# --- Тести /doc ---

async def test_owner_receives_doc_links():
    """Власник отримує посилання на обидва Google Sheets."""
    from handlers.commands import doc

    owner_id = 999
    update = make_update(user_id=owner_id)
    context = make_context()

    with patch("utils.decorators.OWNER_USER_TELEGRAM_IDS", [owner_id]), \
         patch("handlers.commands.GOOGLE_SHEET_ID", "sheet-id-123"), \
         patch("handlers.commands.UU_SCHEDULE_SHEET_ID", "schedule-id-456"):
        await doc(update, context)

    update.message.reply_text.assert_called_once()
    sent_text = update.message.reply_text.call_args[0][0]
    assert "sheet-id-123" in sent_text
    assert "schedule-id-456" in sent_text


async def test_non_owner_cannot_get_doc_links():
    """Не-власник отримує відмову і посилання не надсилаються."""
    from handlers.commands import doc

    owner_id = 999
    stranger_id = 111
    update = make_update(user_id=stranger_id)
    context = make_context()

    with patch("utils.decorators.OWNER_USER_TELEGRAM_IDS", [owner_id]):
        await doc(update, context)

    update.message.reply_text.assert_called_once_with("⛔ У вас немає доступу до цієї команди.")
