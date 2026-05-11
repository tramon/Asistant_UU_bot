# Asistant UU Bot

Telegram-бот для навчальних груп. Надсилає заплановані оголошення та відповідає на команди. Запускається на GitHub Actions.

---

## Структура проекту

```
bot.py                  # Точка входу — main(), реєстрація handlers
scheduler.py            # Планування оголошень через APScheduler
announcements.py        # Конфіг оголошень (текст, cron, чати)
config.py               # Змінні середовища, Google Sheets клієнт, CHATS
run.py                  # Локальний запуск: спочатку тести, потім бот

handlers/
  commands.py           # Обробники команд (/start, /help, /info, /week, /schedule, ...)
  callbacks.py          # Обробники inline-кнопок

utils/
  helpers.py            # get_chat_key_by_id, get_chat_ids
  decorators.py         # allowed_chats_only — фільтр чатів
  utils.py              # get_study_week — логіка підрахунку тижня

tests/
  test_utils.py         # Тести для utils
```

---

## Команди бота

| Команда | Опис |
|---|---|
| `/start` | Перевірити що бот живий |
| `/help` | Список команд |
| `/chatid` | Показати ID поточного чату |
| `/info` | Інформація про групу + inline-кнопки |
| `/week` | Який зараз тиждень навчання |
| `/schedule` | Посилання на розклад групи |

---

## Змінні середовища

Локально — файл `.env`. На GitHub Actions — секрети репозиторію.

| Змінна | Опис |
|---|---|
| `BOT_TOKEN` | Telegram Bot Token від BotFather |
| `BOT_USERNAME` | Username бота (без @) |
| `GOOGLE_SHEET_ID` | ID Google Sheet з конфігом чатів |
| `GOOGLE_CREDENTIALS_JSON` | JSON сервісного акаунту Google (для GitHub Actions) |
| `UU_SCHEDULE_SHEET_ID` | ID Google Sheet з розкладами груп |

Локально замість `GOOGLE_CREDENTIALS_JSON` — файл `google_credentials.json` у корені проекту.

---

## Google Sheets

### Конфіг чатів (`GOOGLE_SHEET_ID`)

Sheet1 повинен містити колонки:

| key | name | telegram_id | info | welcome |
|---|---|---|---|---|
| main | Назва групи | -100123456789 | Текст для /info | Текст привітання |
| dev | Dev група | -100987654321 | ... | ... |

### Розклади (`UU_SCHEDULE_SHEET_ID`)

Окремий Google Sheet. Кожна вкладка (tab) — назва ключа групи (`main`, `dev`). Команда `/schedule` повертає посилання на відповідну вкладку.

---

## Оголошення

Налаштовуються у `announcements.py`. Формат:

```python
{
    "text": "Текст оголошення",   # або lambda: f"Динамічний {текст}"
    "cron": "0 9 * * 1-5",       # cron-вираз (Europe/Kyiv)
    "chats": ["main"],            # ключі груп або ["all"]
}
```

**Cron-шпаргалка:**
```
0 9 * * 1-5    → 09:00 пн-пт
0 17 * * 5     → 17:00 кожної п'ятниці
30 8 * * 1     → 08:30 кожного понеділка
```

---

## Локальний запуск

```bash
pip install -r requirements.txt
python run.py        # запускає тести, потім бота
```

> ⚠️ Не запускай бота локально одночасно з GitHub Actions — виникне конфлікт (409 Conflict).

---

## GitHub Actions

Бот запускається автоматично:
- при пуші в `main`
- за розкладом: кожні 6 годин (cron)
- вручну через `workflow_dispatch`

Кожен новий запуск автоматично зупиняє попередній (`concurrency: cancel-in-progress: true`).

Сесія бота — до 5 годин 55 хвилин, після чого GitHub Actions перезапускає його за розкладом.

---

## Тести

```bash
pytest
```
