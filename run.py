import asyncio
import sys

import pytest


def run_tests() -> bool:
    """Запускає тести перед стартом бота. Повертає True якщо всі пройшли."""
    print("=" * 50)
    print("Запуск тестів...")
    print("=" * 50)
    result = pytest.main(["tests/", "-v"])
    print("=" * 50)
    if result != 0:
        print("❌ Тести не пройшли — бот не запустився")
        return False
    print("✅ Всі тести пройшли — запускаємо бота")
    print("=" * 50)
    return True


if __name__ == "__main__":
    if not run_tests():
        sys.exit(1)

    from bot import main
    asyncio.run(main())
