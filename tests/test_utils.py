from utils.utils import get_study_week, week_1, week_2

import datetime
import pytest
from unittest.mock import patch

from utils.utils import get_study_week


def test_first_week_on_start_date():
    """16.02.2026 - має бути - 1-ий тиждень."""
    with patch("utils.utils.datetime") as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2026, 2, 16)
        mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)
        assert get_study_week() == week_1


def test_second_week():
    """23.02.2026 - має бути - другий тиждень."""
    with patch("utils.utils.datetime") as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2026, 2, 23)
        mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)
        assert get_study_week() == week_2


def test_alternates_correctly():
    """Перевіряємо чергування кількох тижнів поспіль."""
    start = datetime.date(2026, 2, 16)
    expected = [week_1, week_2, week_1, week_2, week_1]

    for i, exp in enumerate(expected):
        day = start + datetime.timedelta(weeks=i)
        with patch("utils.utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = day
            mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)
            assert get_study_week() == exp, f"Тиждень {i + 1}: очікувалось {exp}"
