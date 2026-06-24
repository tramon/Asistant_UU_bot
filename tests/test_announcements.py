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
