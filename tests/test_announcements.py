"""
Тести відправки оголошень.

Тестуємо реальну функцію send_announcement зі scheduler.py.
Використовуємо mock — реальних запитів до Telegram або Google Sheets немає.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def active_users():
    return [
        {"user_id": 111, "username": "alice"},
        {"user_id": 222, "username": "bob"},
        {"user_id": 333, "username": "charlie"},
    ]


async def test_sends_to_group_chat(mock_bot):
    from scheduler import send_announcement
    with patch("scheduler.CHATS", {"main": {"telegram_id": -100111, "name": "Main"}}):
        await send_announcement(mock_bot, "Hello!", [-100111], ["main"], [])
    mock_bot.send_message.assert_called_once_with(chat_id=-100111, text="Hello!")


async def test_no_personal_message_without_users_field(mock_bot):
    from scheduler import send_announcement
    with patch("scheduler.CHATS", {"main": {"telegram_id": -100111, "name": "Main"}}):
        await send_announcement(mock_bot, "Group msg", [-100111], ["main"], [])
    assert mock_bot.send_message.call_count == 1


async def test_sends_to_all_active_users(mock_bot, active_users):
    from scheduler import send_announcement
    with patch("scheduler.get_active_users", return_value=active_users):
        await send_announcement(mock_bot, "Hi all!", [], [], ["all"])
    assert mock_bot.send_message.call_count == 3
    called_ids = {call.kwargs["chat_id"] for call in mock_bot.send_message.call_args_list}
    assert called_ids == {111, 222, 333}


async def test_sends_to_specific_user_by_username(mock_bot, active_users):
    from scheduler import send_announcement
    with patch("scheduler.get_active_users", return_value=active_users):
        await send_announcement(mock_bot, "Only you", [], [], ["alice"])
    mock_bot.send_message.assert_called_once_with(chat_id=111, text="Only you")


async def test_sends_to_specific_user_with_at_sign(mock_bot, active_users):
    from scheduler import send_announcement
    with patch("scheduler.get_active_users", return_value=active_users):
        await send_announcement(mock_bot, "Hi Bob", [], [], ["@bob"])
    mock_bot.send_message.assert_called_once_with(chat_id=222, text="Hi Bob")


async def test_sends_to_multiple_specific_users(mock_bot, active_users):
    from scheduler import send_announcement
    with patch("scheduler.get_active_users", return_value=active_users):
        await send_announcement(mock_bot, "For two", [], [], ["alice", "charlie"])
    assert mock_bot.send_message.call_count == 2
    called_ids = {call.kwargs["chat_id"] for call in mock_bot.send_message.call_args_list}
    assert called_ids == {111, 333}


async def test_unknown_username_sends_nothing(mock_bot, active_users):
    from scheduler import send_announcement
    with patch("scheduler.get_active_users", return_value=active_users):
        await send_announcement(mock_bot, "Nobody", [], [], ["unknown"])
    mock_bot.send_message.assert_not_called()


async def test_lambda_text_evaluated_at_send_time(mock_bot, active_users):
    from scheduler import send_announcement
    counter = {"n": 0}

    def dynamic_text():
        counter["n"] += 1
        return f"Call #{counter['n']}"

    with patch("scheduler.get_active_users", return_value=active_users):
        await send_announcement(mock_bot, dynamic_text, [], [], ["alice"])
    mock_bot.send_message.assert_called_once_with(chat_id=111, text="Call #1")


async def test_draft_sends_only_to_owners(mock_bot):
    """DRAFT оголошення надсилається тільки власникам з префіксом [DRAFT]."""
    from scheduler import send_announcement
    owner_ids = [999, 888]

    with patch("scheduler.OWNER_USER_TELEGRAM_IDS", owner_ids):
        await send_announcement(mock_bot, "Тест DRAFT", [], [], ["__owners__"])

    assert mock_bot.send_message.call_count == 2
    called_ids = {call.kwargs["chat_id"] for call in mock_bot.send_message.call_args_list}
    assert called_ids == {999, 888}
    # Перевіряємо префікс [DRAFT] у тексті
    sent_text = mock_bot.send_message.call_args_list[0].kwargs["text"]
    assert "[DRAFT]" in sent_text
    assert "Тест DRAFT" in sent_text


async def test_draft_does_not_call_get_active_users(mock_bot):
    """DRAFT не звертається до get_active_users — власники визначаються через OWNER_USER_TELEGRAM_IDS."""
    from scheduler import send_announcement

    with patch("scheduler.OWNER_USER_TELEGRAM_IDS", [999]), \
         patch("scheduler.get_active_users") as mock_get_users:
        await send_announcement(mock_bot, "Draft msg", [], [], ["__owners__"])

    mock_get_users.assert_not_called()


async def test_draft_sends_nothing_when_no_owners(mock_bot):
    """Якщо OWNER_USER_TELEGRAM_IDS порожній — DRAFT нікуди не надсилається."""
    from scheduler import send_announcement

    with patch("scheduler.OWNER_USER_TELEGRAM_IDS", []):
        await send_announcement(mock_bot, "Draft msg", [], [], ["__owners__"])

    mock_bot.send_message.assert_not_called()


# --- Тест логіки active-статусу (через load_announcements_from_sheet) ---

def _make_row(active: str, text: str = "Тест", cron: str = "0 9 * * 1") -> dict:
    return {"id": "1", "text": text, "cron": cron, "chats": "main", "users": "", "active": active}


def test_active_empty_is_included():
    """Порожній active → оголошення надсилається (за замовчуванням активне)."""
    from config import load_announcements_from_sheet
    from unittest.mock import MagicMock, patch

    rows = [_make_row(active="")]
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = rows

    with patch("config.get_google_client") as mock_client:
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_ws
        result = load_announcements_from_sheet()

    assert result is not None and len(result) == 1


def test_active_true_is_included():
    """TRUE → оголошення надсилається."""
    from config import load_announcements_from_sheet
    from unittest.mock import MagicMock, patch

    rows = [_make_row(active="TRUE")]
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = rows

    with patch("config.get_google_client") as mock_client:
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_ws
        result = load_announcements_from_sheet()

    assert result is not None and len(result) == 1


def test_active_false_is_excluded():
    """FALSE → оголошення пропускається."""
    from config import load_announcements_from_sheet
    from unittest.mock import MagicMock, patch

    rows = [_make_row(active="FALSE")]
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = rows

    with patch("config.get_google_client") as mock_client:
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_ws
        result = load_announcements_from_sheet()

    assert result is not None and len(result) == 0


def test_active_unknown_value_is_excluded():
    """Будь-яке невідоме значення (PENDING, YES, 1...) → пропускається."""
    from config import load_announcements_from_sheet
    from unittest.mock import MagicMock, patch

    rows = [_make_row(active="PENDING"), _make_row(active="YES"), _make_row(active="1")]
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = rows

    with patch("config.get_google_client") as mock_client:
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_ws
        result = load_announcements_from_sheet()

    assert result is not None and len(result) == 0


def test_active_draft_goes_to_owners_only():
    """DRAFT → chats=[], users=['__owners__']."""
    from config import load_announcements_from_sheet
    from unittest.mock import MagicMock, patch

    rows = [_make_row(active="DRAFT")]
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = rows

    with patch("config.get_google_client") as mock_client:
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_ws
        result = load_announcements_from_sheet()

    assert result is not None and len(result) == 1
    ann = result[0]
    assert ann["chats"] == []
    assert ann["users"] == ["__owners__"]
