# AGENTS.md — Asistant UU Bot

## Quick Architecture

**Asistant UU Bot** is a Ukrainian-language Telegram bot for educational groups that sends scheduled announcements and responds to commands. It runs on GitHub Actions using async polling.

```
bot.py (main) 
    ↓
handlers/ (commands, inline buttons)
    ↓
scheduler (APScheduler, cron-based announcements)
    ↓
config (Google Sheets for dynamic chat config)
```

---

## Quick Start

**You need these before running:**
- Python 3.11
- `.env` file in the project root (see variables below)
- `google_credentials.json` in the project root (Google Cloud service account key)

**`.env` file:**
```
BOT_TOKEN=...
BOT_USERNAME=...
GOOGLE_SHEET_ID=...
UU_SCHEDULE_SHEET_ID=...
OWNER_USER_TELEGRAM_IDS=123456,654321
```

**Setup and run:**
```bash
pip install -r requirements.txt
python run.py          # runs pytest first, then starts bot with polling
```

**Or separately:**
```bash
pytest tests/ -v       # tests only
python bot.py          # bot only (skip test runner)
```

**Verify it works:** bot logs `Бот запущено. Polling...` and `Планувальник запущено` on startup.

> **Do not run locally while GitHub Actions is executing** — Telegram rejects concurrent polling with a 409 Conflict error.

---

## Core Data Flow

1. **Chat Configuration**: Loaded at startup in `config.py` → `CHATS` dict (keyed by group name: `"main"`, `"dev"`, etc.)
2. **User Commands**: Handlers in `handlers/commands.py` receive updates, check `allowed_chats_only` decorator
3. **Scheduled Announcements**: `scheduler.py` reads `ANNOUNCEMENTS` list, sends messages at cron times (Europe/Kyiv timezone)
4. **Inline Buttons**: Commands return `InlineKeyboardMarkup` → callbacks in `handlers/callbacks.py` modify message text

**Google Sheets Integration**:
- `GOOGLE_SHEET_ID`: Chat metadata (name, Telegram ID, info text, welcome message)
- `UU_SCHEDULE_SHEET_ID`: Per-group schedule sheets (one sheet per chat key)

---

## Key Patterns & Conventions

### 1. **Authorization via Decorators**
Commands use composable decorators from `utils/decorators.py`:
```python
@allowed_chats_only           # Checks Telegram chat ID against ALLOWED_CHAT_IDS
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...

@private_chat_only            # Ensures private DM, not group chat
@allowed_users_only           # Limited to OWNER_USER_TELEGRAM_IDS
async def doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only owners in private chat can call /doc
```

### 2. **Chat Lookup Pattern**
Because chats are keyed by string ("main", "dev"), two utility functions:
```python
# utils/chat_resolver.py
get_chat_key_by_id(telegram_id)  # "main" ← -100123456789
get_chat_ids(["main"])            # [-100123456789] ← list of keys
```

### 3. **Scheduled Announcements with Dynamic Content**
Text can be **static string or lambda** (evaluated at send time):
```python
{
    "text": lambda: f"Week {get_study_week()}: {get_day_of_week()}",
    "cron": "25 8 * * 1-4",  # crontab format in pytz
    "chats": ["all"],        # or ["main", "dev"] or specific keys
}
```

### 4. **Misfire Grace Time (Important)**
```python
# scheduler.py: misfire_grace_time=600 (10 minutes)
```
If a scheduled task is missed by <10 min (e.g., during GitHub Actions restart between sessions), it fires immediately. >10 min = skipped (no stale messages). This handles the 5:55 session limit gracefully.

### 5. **Study Week Logic**
Two-week alternating schedule, based on fixed start date (currently 2026-02-16):
```python
# utils/utils.py
get_study_week()  # Returns "1-й" or "2-й" based on (today - start_date) // 7 % 2
```
**To update academic year, change `start_date` in `get_study_week()`.**

### 6. **Inline Button Pattern**
Commands send buttons with callback_data → callback handler modifies message:
```python
# commands.py
keyboard = [[InlineKeyboardButton("📅 Який зараз тиждень?", callback_data="week")]]
await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# callbacks.py
async def week_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await query.edit_message_text(...)  # Edit original message in-place
```

---

## Adding Features: Common Tasks

**Add a new scheduled announcement:**
```python
# announcements.py
{
    "text": "Your message",
    "cron": "0 17 * * 4",  # 5 PM every Friday
    "chats": ["main"],
}
```

**Add a new command:**
```python
# handlers/commands.py
@allowed_chats_only
async def mycommand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Response")

# bot.py
app.add_handler(CommandHandler("mycommand", mycommand))
```

**Add a new chat group:**
1. Add row to Google Sheet (`GOOGLE_SHEET_ID`) with columns: `key`, `name`, `telegram_id`, `info`, `welcome`
2. Create corresponding worksheet in `UU_SCHEDULE_SHEET_ID` with sheet name = key
3. Restart bot to reload `CHATS` from Google Sheets

**Limit command to owners only (private DM):**
```python
@private_chat_only
@allowed_users_only
async def sensitive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...
```

---

## Critical Gotchas

1. **No Concurrent Runs**: Don't run bot locally while GitHub Actions is executing (409 Conflict error)
2. **Credentials Loading**: `google_credentials.json` file locally OR `GOOGLE_CREDENTIALS_JSON` env var in GitHub Actions
3. **Chat Config is Cached**: `CHATS` and `ALLOWED_CHAT_IDS` loaded at startup. New Google Sheet changes require bot restart.
4. **Timezone Hardcoded**: All cron timings use `Europe/Kyiv` (pytz)
5. **Update Filtering**: Callback handlers have no `@allowed_chats_only` — they inherit from the command that spawned them

---

## File Reference Guide

| File | Purpose | Key Exports |
|------|---------|-------------|
| `bot.py` | Async entry point | `main()` — sets up telegram.ext handlers |
| `config.py` | Environment + Google Sheets client | `CHATS`, `ALLOWED_CHAT_IDS`, `get_schedule_url()` |
| `announcements.py` | List of scheduled messages | `ANNOUNCEMENTS` (list of dicts with text/cron/chats) |
| `scheduler.py` | APScheduler setup + send logic | `setup_scheduler(bot)` |
| `handlers/commands.py` | Command handlers | `/start`, `/help`, `/chatid`, `/info`, `/week`, `/schedule`, `/doc` |
| `handlers/callbacks.py` | Inline button handlers | `week_callback`, `schedule_callback` |
| `utils/decorators.py` | Authorization helpers | `@allowed_chats_only`, `@private_chat_only`, `@allowed_users_only` |
| `utils/chat_resolver.py` | Chat ID ↔ key mapping | `get_chat_key_by_id()`, `get_chat_ids()` |
| `utils/utils.py` | General utilities | `get_study_week()`, `get_day_of_week()` |

---

## CI / GitHub Actions

- **Triggers**: Push to `main`, schedule (every 6 hours), manual dispatch
- **Concurrency**: `cancel-in-progress: true` — only one bot instance runs at a time
- **Session limit**: 5 hours 55 minutes, then auto-restarts (next scheduled trigger)
- **Credentials**: `GOOGLE_CREDENTIALS_JSON` secret (JSON string) instead of the local file

---

## Testing & Debugging

- **Test suite**: `tests/test_utils.py` (focuses on week calculation logic)
- **Logging**: All modules use Python `logging`; `getUpdates` spam is filtered in `bot.py` (`_FilterGetUpdates`)
- **Cron validation**: https://crontab.guru/
