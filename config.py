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
