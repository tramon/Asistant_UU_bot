import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ALLOWED_CHAT_IDS, CHATS, GOOGLE_SHEET_ID, UU_SCHEDULE_SHEET_ID, get_schedule_url, upsert_user
from scheduler import setup_scheduler, send_announcement
from utils.chat_resolver import get_chat_key_by_id, get_chat_ids
from utils.decorators import allowed_chats_only, allowed_users_only, private_chat_only
from utils.utils import get_study_week

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        # Особистий чат — реєструємо користувача, дозволено всім
        user = update.effective_user
        upsert_user(user.id, user.username, user.first_name)
        await update.message.reply_text("Бот активний ✅")
    elif update.effective_chat.id in ALLOWED_CHAT_IDS:
        # Група — тільки дозволені
        await update.message.reply_text("Бот активний ✅")
    else:
        logger.warning(f"Заблоковано /start з групи {update.effective_chat.id}")
        return


@allowed_chats_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Доступні команди:\n"
        "/start — перевірити що бот живий\n"
        "/help — список команд\n"
        "/chatid — показати ID цього чату\n"
        "/info — інформація про цю групу\n"
        "/week — який зараз тиждень навчання\n"
        "/schedule — розклад групи\n"
    )
    await update.message.reply_text(text)


@allowed_chats_only
async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(
        f"Chat ID: `{chat.id}`\nНазва: {chat.title or chat.first_name}",
        parse_mode="Markdown"
    )


@allowed_chats_only
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає інформацію специфічну для групи."""
    chat_key = get_chat_key_by_id(update.effective_chat.id)
    if chat_key is None:
        await update.message.reply_text("ℹ️ Ця група не налаштована.")
        return
    text = CHATS[chat_key].get("info", "ℹ️ Немає інформації для цієї групи.")
    keyboard = [
        [InlineKeyboardButton("📅 Який зараз тиждень?", callback_data="week")],
        [InlineKeyboardButton("📋 Розклад", callback_data="schedule")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


@allowed_chats_only
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає інформацію про поточний тиждень навчання."""
    current_week = get_study_week()
    await update.message.reply_text(f"📅 Зараз {current_week} тиждень навчання.")


@allowed_chats_only
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає посилання на розклад групи."""
    chat_key = get_chat_key_by_id(update.effective_chat.id)
    if chat_key is None:
        await update.message.reply_text("ℹ️ Ця група не налаштована.")
        return
    url = get_schedule_url(chat_key)
    if url is None:
        await update.message.reply_text("❌ Розклад для цієї групи не знайдено.")
        return
    text = f"📅 Розклад:\n{chat_key}\n{url}"
    await update.message.reply_text(text, disable_web_page_preview=True)


@private_chat_only
@allowed_users_only
async def doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає посилання на Google Sheets (тільки для дозволених користувачів)."""
    chats_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"
    schedule_url = f"https://docs.google.com/spreadsheets/d/{UU_SCHEDULE_SHEET_ID}"
    text = (
        "📄 Документи:\n\n"
        f"Конфіг чатів:\n{chats_url}\n\n"
        f"Розклад:\n{schedule_url}"
    )
    await update.message.reply_text(text, disable_web_page_preview=True)


@private_chat_only
@allowed_users_only
async def reload_scheduler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезапускає планувальник оголошень без перезапуску бота."""
    old_scheduler = context.bot_data.get("scheduler")
    if old_scheduler and old_scheduler.running:
        old_scheduler.shutdown(wait=False)
        logger.info("Старий планувальник зупинено")

    new_scheduler = setup_scheduler(context.bot)
    new_scheduler.start()
    context.bot_data["scheduler"] = new_scheduler
    logger.info("Планувальник перезапущено через /reload")

    await update.message.reply_text("✅ Планувальник перезапущено")


@allowed_chats_only
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Невідома команда. Спробуй /help")


@private_chat_only
@allowed_users_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Надсилає повідомлення в чат або користувачу від імені бота.

    Використання: /broadcast <одержувач> <повідомлення>

    Одержувачі:
      all            — всі групові чати
      users          — всім активним користувачам особисто
      main / dev     — конкретний чат (ключ з CHATS)
      <username>     — конкретному користувачу особисто
    """

    args = context.args  # ["main", "Привіт", "групі!"]

    if not args or len(args) < 2:
        await update.message.reply_text(
            "Використання: /broadcast <одержувач> <повідомлення>\n\n"
            "Приклади:\n"
            "  /broadcast all Привіт усім групам!\n"
            "  /broadcast users Привіт усім особисто!\n"
            "  /broadcast main Привіт групі main!\n"
            "  /broadcast andriitramon Привіт особисто!"
        )
        return

    # Перший аргумент може містити кількох одержувачів через кому: @alice,@bob
    recipients = [r.strip() for r in args[0].split(",") if r.strip()]
    text = " ".join(args[1:])

    # Визначаємо chat_ids / chat_keys / user_keys за одержувачем
    if recipients == ["all"]:
        chat_ids = get_chat_ids(["all"])
        chat_keys = ["all"]
        user_keys = []
        target_label = "всі групи"
    elif recipients == ["users"]:
        chat_ids = []
        chat_keys = []
        user_keys = ["all"]
        target_label = "всі активні користувачі"
    elif all(r in CHATS for r in recipients):
        chat_ids = get_chat_ids(recipients)
        chat_keys = recipients
        user_keys = []
        target_label = ", ".join(f"чат '{r}'" for r in recipients)
    else:
        # Вважаємо usernames
        chat_ids = []
        chat_keys = []
        user_keys = recipients
        target_label = ", ".join(f"@{r.lstrip('@')}" for r in recipients)
    await send_announcement(context.bot, text, chat_ids, chat_keys, user_keys)
    await update.message.reply_text(f"✅ Надіслано → {target_label}")
