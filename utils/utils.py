import datetime

week_1 = "1"
week_2 = "2"

DAY_NAMES = {
    0: "Пн.",
    1: "Вт.",
    2: "Ср.",
    3: "Чт.",
    4: "Пт.",
    5: "Сб.",
    6: "Нд.",
}


def get_study_week() -> str:
    """Повертає '1-й' або '2-й' тиждень навчання відносно дати старту."""
    start_date = datetime.date(2026, 2, 16)
    today = datetime.date.today()
    days_diff = (today - start_date).days
    week_num = (days_diff // 7) + 1
    return week_1 if week_num % 2 != 0 else week_2


def get_day_of_week() -> str:
    """Повертає скорочену назву поточного дня тижня (Пн. Вт. Ср. Чт. Пт. Сб. Нд.)"""
    return DAY_NAMES[datetime.date.today().weekday()]
