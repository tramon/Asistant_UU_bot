import json
import logging
import os

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
GOOGLE_SHEET_ID: str | None = os.getenv("GOOGLE_SHEET_ID")
UU_SCHEDULE_SHEET_ID: str | None = os.getenv("UU_SCHEDULE_SHEET_ID")

# Список Telegram user_id, яким дозволено /doc. Формат у .env: OWNER_USER_TELEGRAM_IDS=123456,789012
_raw_owner_ids = os.getenv("OWNER_USER_TELEGRAM_IDS", "")
logger.info(f"[config] OWNER_USER_TELEGRAM_IDS raw value: '{_raw_owner_ids}'")
OWNER_USER_TELEGRAM_IDS: list[int] = [
    int(uid.strip())
    for uid in _raw_owner_ids.split(",")
    if uid.strip().isdigit()
]
logger.info(f"[config] OWNER_USER_TELEGRAM_IDS parsed: {OWNER_USER_TELEGRAM_IDS}")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = "google_credentials.json"


def load_google_credentials() -> dict:
    """
    Локально — читає з файлу google_credentials.json
    GitHub Actions — читає з змінної середовища GOOGLE_CREDENTIALS_JSON
    """
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            return json.load(f)

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        return json.loads(creds_json)

    raise FileNotFoundError(
        "Credentials не знайдено. Додай google_credentials.json або GOOGLE_CREDENTIALS_JSON в env"
    )


def get_google_client():
    """Створює авторизований gspread клієнт."""
    creds_data = load_google_credentials()
    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    return gspread.authorize(creds)


# --- Статуси користувачів ---
USER_STATUS_INACTIVE = "не активний"
USER_STATUS_ACTIVE   = "активний"
USER_STATUS_BLOCKED  = "заблокований"


def _get_users_worksheet():
    """Повертає вкладку 'users' з основного Google Sheet."""
    client = get_google_client()
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet("users")


def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """
    Якщо користувач вже є в Sheet — оновлює статус на 'активний' і joined_at.
    Якщо нема — НЕ додає (адмін додає вручну).
    """
    import datetime
    try:
        ws = _get_users_worksheet()
        records = ws.get_all_records()
        for i, row in enumerate(records, start=2):  # рядок 1 — заголовок
            if str(row.get("user_id")) == str(user_id):
                ws.update(f"D{i}", [[USER_STATUS_ACTIVE]])
                if not row.get("joined_at"):
                    ws.update(f"E{i}", [[datetime.date.today().isoformat()]])
                logger.info(f"Користувач {user_id} ({first_name}) → статус: {USER_STATUS_ACTIVE}")
                return
        logger.info(f"Користувач {user_id} не знайдений в Sheet — пропущено")
    except Exception as e:
        logger.error(f"Помилка upsert_user({user_id}): {e}")


def get_active_users() -> list[int]:
    """Повертає список {'user_id': int, 'username': str} з статусом 'активний'."""
    try:
        ws = _get_users_worksheet()
        records = ws.get_all_records()
        active = [
            {"user_id": int(row["user_id"]), "username": row.get("username") or str(row["user_id"])}
            for row in records
            if row.get("status") == USER_STATUS_ACTIVE
        ]
        logger.info(f"Активних користувачів: {len(active)}")
        return active
    except Exception as e:
        logger.error(f"Помилка get_active_users: {e}")
        return []


def update_user_status(user_id: int, status: str) -> None:
    """Оновлює статус користувача в Sheet."""
    try:
        ws = _get_users_worksheet()
        records = ws.get_all_records()
        for i, row in enumerate(records, start=2):
            if str(row.get("user_id")) == str(user_id):
                username = row.get("username") or str(user_id)
                ws.update(f"D{i}", [[status]])
                logger.info(f"@{username} (id={user_id}) → статус: {status}")
                return
        logger.warning(f"update_user_status: користувач {user_id} не знайдений")
    except Exception as e:
        logger.error(f"Помилка update_user_status({user_id}): {e}")


def get_schedule_url(chat_key: str) -> str | None:
    """Повертає посилання на аркуш розкладу для групи за її ключем."""
    try:
        client = get_google_client()
        sheet = client.open_by_key(UU_SCHEDULE_SHEET_ID)
        worksheet = sheet.worksheet(chat_key)
        gid = worksheet.id
        return f"https://docs.google.com/spreadsheets/d/{UU_SCHEDULE_SHEET_ID}/edit#gid={gid}"
    except Exception as e:
        logger.error(f"Помилка отримання розкладу для '{chat_key}': {e}")
        return None


def load_chats_from_sheet() -> dict:
    """Читає чати з Google Sheet і повертає dict."""
    try:
        client = get_google_client()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        records = sheet.get_all_records()

        chats = {}
        for row in records:
            key = row["key"]
            chats[key] = {
                "name":        row["name"],
                "telegram_id": int(row["telegram_id"]),
                "info":        row.get("info", ""),
                "welcome":     row.get("welcome", ""),
            }

        logger.info(f"Завантажено {len(chats)} чатів з Google Sheet")
        return chats

    except Exception as e:
        logger.error(f"Помилка читання Google Sheet: {e}")
        return {}


# --- Завантажуємо при старті ---
CHATS = load_chats_from_sheet()
ALLOWED_CHAT_IDS = [v["telegram_id"] for v in CHATS.values()]
