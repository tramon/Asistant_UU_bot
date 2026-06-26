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
USER_STATUS_ACTIVE   = "активний"      # підтверджений адміном, отримує розсилку
USER_STATUS_BLOCKED  = "заблокований"  # заблокував бота — адмін вирішує що далі


def load_announcements_from_sheet() -> list[dict] | None:
    """
    Читає оголошення з вкладки 'announcements' Google Sheet.
    Повертає список dict у форматі сумісному з announcements.py, або None при помилці.

    Структура вкладки: id | text | cron | chats | users | active
    - chats: comma-separated ключі груп або 'all' або порожньо
    - users: comma-separated username або 'all' або порожньо
    - active: TRUE/FALSE/DRAFT
        - порожньо або TRUE  → активне (надсилається всім)
        - FALSE              → вимкнено (пропускається)
        - DRAFT              → тільки власникам в особисті (chats ігноруються)
    - text: підтримує плейсхолдери {day} і {week}
    """
    from utils.utils import get_day_of_week, get_study_week

    try:
        client = get_google_client()
        ws = client.open_by_key(GOOGLE_SHEET_ID).worksheet("announcements")
        records = ws.get_all_records()

        announcements = []
        for row in records:
            active_val = str(row.get("active", "")).strip().upper()
            if active_val not in ("", "TRUE", "DRAFT"):
                continue

            raw_text = str(row.get("text", "")).strip()
            cron = str(row.get("cron", "")).strip()

            if not raw_text or not cron:
                logger.warning(f"Пропущено рядок без тексту або cron: {row}")
                continue

            # Плейсхолдери {day} і {week} → lambda щоб обраховувались в момент надсилання
            if "{day}" in raw_text or "{week}" in raw_text:
                template = raw_text
                text = lambda t=template: t.format(day=get_day_of_week(), week=get_study_week())
            else:
                text = raw_text

            # DRAFT → надсилається тільки власникам в особисті, групи ігноруються
            if active_val == "DRAFT":
                ann = {"text": text, "cron": cron, "chats": [], "users": ["__owners__"]}
                ann_id = str(row.get("id", "")).strip()
                if ann_id:
                    ann["id"] = ann_id
                logger.info(f"DRAFT оголошення (id={ann_id or '?'}): тільки для власників")
                announcements.append(ann)
                continue

            # chats: "main,dev" → ["main", "dev"], "" → []
            raw_chats = str(row.get("chats", "")).strip()
            chats = [c.strip() for c in raw_chats.split(",") if c.strip()] if raw_chats else []

            # users: "all" → ["all"], "alice,bob" → ["alice", "bob"], "" → []
            raw_users = str(row.get("users", "")).strip()
            users = [u.strip() for u in raw_users.split(",") if u.strip()] if raw_users else []

            ann = {"text": text, "cron": cron, "chats": chats}
            if users:
                ann["users"] = users

            announcements.append(ann)

        logger.info(f"Завантажено {len(announcements)} оголошень з Google Sheet")
        return announcements

    except Exception as e:
        logger.error(f"Помилка завантаження оголошень з Sheet: {e}")
        return None


def _get_users_worksheet():
    """Повертає вкладку 'users' — підтверджені користувачі."""
    client = get_google_client()
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet("users")


def _get_requests_worksheet():
    """Повертає вкладку 'requests' — черга запитів від /start."""
    client = get_google_client()
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet("requests")


def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """
    Записує користувача у вкладку 'requests' (черга).
    Якщо вже є — оновлює username/first_name (дані могли змінитись).
    Вкладку 'users' не чіпає — адмін керує нею вручну.
    """
    import datetime
    today = datetime.date.today().isoformat()
    try:
        ws = _get_requests_worksheet()
        records = ws.get_all_records()
        for i, row in enumerate(records, start=2):
            if str(row.get("user_id")) == str(user_id):
                # Оновлюємо username і first_name — могли змінитись
                ws.update(f"B{i}:C{i}", [[username or "", first_name or ""]])
                logger.info(f"@{username or user_id} (id={user_id}) повторно натиснув /start — оновлено дані")
                return
        # Новий — додаємо в чергу
        ws.append_row([user_id, username or "", first_name or "", today])
        logger.info(f"Новий запит: @{username or user_id} (id={user_id}) → додано в requests")
    except Exception as e:
        logger.error(f"Помилка upsert_user({user_id}): {e}")


def get_active_users() -> list[dict]:
    """Повертає список {'user_id': int, 'username': str} зі статусом 'активний' з вкладки 'users'."""
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
    """Читає чати з Google Sheet і повертає dict.

    Колонка status (F):
      - порожньо або TRUE → чат дозволений
      - будь-яке інше (FALSE, DISABLED тощо) → чат вимкнений, ігнорується
    """
    try:
        client = get_google_client()
        sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("groups")
        records = sheet.get_all_records()

        chats = {}
        for row in records:
            status = str(row.get("status", "")).strip().upper()
            if status not in ("", "TRUE"):
                logger.warning(f"Чат '{row.get('key')}' вимкнений (status={status!r}) — пропускається")
                continue
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
