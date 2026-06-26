"""
Перевіряє що критичні файли проекту синтаксично валідні та не обрізані.
"""

import ast
import os

CRITICAL_FILES = [
    "bot.py",
    "scheduler.py",
    "config.py",
    "announcements.py",
    "handlers/commands.py",
    "handlers/callbacks.py",
    "utils/decorators.py",
    "utils/chat_resolver.py",
    "utils/utils.py",
]


def test_all_critical_files_are_valid_python():
    """Перевіряє що жоден критичний файл не обрізаний і синтаксично валідний."""
    base = os.path.dirname(os.path.dirname(__file__))  # корінь проекту
    for relative_path in CRITICAL_FILES:
        full_path = os.path.join(base, relative_path)
        with open(full_path, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            raise AssertionError(f"Синтаксична помилка в {relative_path}: {e}")
