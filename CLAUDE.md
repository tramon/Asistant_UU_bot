# Asistant UU Bot — контекст для ШІ

Telegram-бот для навчальних груп. Надсилає заплановані оголошення, відповідає на команди. Запускається на GitHub Actions сесіями по 5г 55хв.

---

## Стек

- Python 3.11
- python-telegram-bot 21.6 (async, polling)
- APScheduler 3.10 (AsyncIOScheduler + CronTrigger)
- gspread + google-auth (сервісний акаунт)
- pytest + pytest-asyncio

---

## Архітектура

```
bot.py              → точка входу: main(), реєстрація handlers, запуск polling
scheduler.py        → setup_scheduler() + send_announcement() (винесена для тестування)
announcements.py    → список оголошень ANNOUNCEMENTS (тільки конфіг, без логіки)
config.py           → env змінні, Google Sheets клієнт, CHATS dict, user functions

handlers/
  commands.py       → всі command handlers
  callbacks.py      → inline keyboard callbacks

utils/
  chat_resolver.py  → get_chat_key_by_id(), get_chat_ids() — резолвить CHATS
  decorators.py     → allowed_chats_only, allowed_users_only, private_chat_only
  utils.py          → get_study_week(), get_day_of_week()

tests/
  test_utils.py
  test_announcements.py  → тестує send_announcement() через mock
```

### Ключові залежності між файлами

- `config.py` виконує `CHATS = load_chats_from_sheet()` при імпорті → якщо немає credentials, повертає `{}`
- `chat_resolver.py` імпортує `CHATS` з `config` на рівні модуля
- `scheduler.py` імпортує `CHATS` і `get_active_users` з `config`
- `announcements.py` не імпортує нічого з `config` — тільки з `utils`

---

## Google Sheets структура

### GOOGLE_SHEET_ID — основний конфіг

**Вкладка `groups`**: `key | name | telegram_id | info | welcome`
- `key` — рядковий ключ (`main`, `dev`), використовується скрізь в коді

**Вкладка `users`**: `user_id | username | first_name | status`
- статуси: `активний` / `заблокований`
- керується вручну адміном
- `get_active_users()` повертає тільки `активний`

**Вкладка `requests`**: `user_id | username | first_name | joined_at`
- записується автоматично через `upsert_user()` при `/start` в особистому чаті
- адмін лише читає, щоб переносити в `users`

### UU_SCHEDULE_SHEET_ID — розклади

Кожна вкладка = ключ групи (`main`, `dev`). `/schedule` повертає посилання на вкладку.

---

## Оголошення (announcements.py)

```python
{
    "text": "рядок або lambda",
    "cron": "25 8 * * 1-4",   # APScheduler cron, TZ=Europe/Kyiv, 0=пн
    "chats": ["main"],         # або ["all"]
    "users": ["all"],          # необов'язково: ["all"] або ["username", "@username"]
}
```

- `text` як lambda → викликається в момент надсилання, не при старті
- `users` → фільтрується через `get_active_users()`, потім по username (lstrip "@", lower)
- `chats: []` + `users: [...]` → тільки особисті, без групових

---

## Контекст запуску (GitHub Actions)

- Файл: `.github/workflows/bot.yml`
- Тригери: push в `main`, cron кожні 6 годин, workflow_dispatch
- `concurrency: cancel-in-progress: true` → новий запуск вбиває попередній
- Сесія: `timeout 21300 python bot.py` (5г 55хв), потім cron перезапускає
- `misfire_grace_time=600` → якщо задача пропущена < 10хв — виконати, інакше пропустити
- Секрети в `env:` секції кроку `Run bot` (не `Run tests`)
- `drop_pending_updates=True` в polling → повідомлення до старту відкидаються

### Змінні середовища

```
BOT_TOKEN
BOT_USERNAME
GOOGLE_SHEET_ID
GOOGLE_CREDENTIALS_JSON    # JSON сервісного акаунту, локально — google_credentials.json
UU_SCHEDULE_SHEET_ID
OWNER_USER_TELEGRAM_IDS    # comma-separated: 123456,789012
```

---

## Правила для змін коду

- `send_announcement()` в `scheduler.py` — публічна функція, не closure. Зміни тут потребують оновлення тестів у `test_announcements.py`
- Новий handler → зареєструвати в `bot.py` через `app.add_handler()`
- Нова команда лише для власників → декоратори `@private_chat_only` + `@allowed_users_only`
- `upsert_user()` пише тільки в `requests`, ніколи в `users` — це навмисно
- `update_user_status()` пише в колонку `D` вкладки `users` (A=user_id, B=username, C=first_name, D=status)
- `CHATS` завантажується один раз при старті — зміни в Sheet потребують перезапуску бота
- Логування: `logger = logging.getLogger(__name__)` в кожному файлі, рівень INFO
- `_FilterGetUpdates` в `bot.py` — пропускає перший `getUpdates` лог, решту фільтрує

---

## Тести

```bash
pytest tests/ -v
```

- `pytest.ini`: `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`
- Тести мокають `scheduler.get_active_users` і `scheduler.CHATS` — Google Sheets не потрібен
- В CI тести запускаються без секретів → `config.py` завантажується з `CHATS = {}` (graceful fallback)
