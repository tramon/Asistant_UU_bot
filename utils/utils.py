import datetime

week_1 = "1-й"
week_2 = "2-й"

def get_study_week() -> str:
    """Повертає '1-й' або '2-й' тиждень навчання відносно дати старту."""
    start_date = datetime.date(2026, 2, 16)
    today = datetime.date.today()
    days_diff = (today - start_date).days
    week_num = (days_diff // 7) + 1
    return week_1 if week_num % 2 != 0 else week_2
