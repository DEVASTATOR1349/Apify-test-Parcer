"""Точка входа парсера подписчиков.

Запуск:  python src/main.py
По крону: PYTHONPATH=src python src/main.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from loguru import logger

# Настраиваем логирование
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{message}</cyan>",
    level="INFO",
)
logger.add(
    "logs/parser_{time:YYYY-MM-DD}.log",
    rotation="30 days",
    retention="3 months",
    level="DEBUG",
)

from config import APIFY_API_TOKEN, MAX_RETRIES, REQUEST_DELAY
from sheets import read_links_sheet, write_results, log_error
from parser import fetch_followers, get_platform_name


def run():
    """Главная функция — однократный прогон парсера."""
    logger.info("=" * 50)
    logger.info("Запуск парсера подписчиков")

    # Проверка наличия токена
    if not APIFY_API_TOKEN:
        logger.error("APIFY_API_TOKEN не задан! Укажи в .env")
        return

    logger.info(f"Лимиты: макс ретраев={MAX_RETRIES}, задержка={REQUEST_DELAY}с")

    # 1. Читаем список проектов из Google Sheets
    projects = read_links_sheet()
    if not projects:
        logger.warning("Нет проектов для парсинга")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_results = []
    total_links = sum(len(p["links"]) for p in projects)

    logger.info(
        f"Найдено проектов: {len(projects)}, всего ссылок: {total_links}"
    )

    # 2. Парсим каждый проект
    processed = 0
    for project in projects:
        name = project["name"]
        links = project["links"]

        logger.info(f"\n--- {name} ({len(links)} площадок) ---")

        for link in links:
            processed += 1
            logger.info(
                f"[{processed}/{total_links}] {name} -> {link[:70]}..."
            )

            platform_name = get_platform_name(link)
            followers = fetch_followers(link, name)

            if followers is not None:
                all_results.append({
                    "date": today,
                    "client": name,
                    "platform": platform_name,
                    "followers": str(followers),
                })
                logger.success(
                    f"  ✅ {platform_name}: {followers} подписчиков"
                )
            else:
                log_error(name, link, "Не удалось получить подписчиков")

    # 3. Записываем в Google Sheets
    if all_results:
        logger.info(f"\nЗапись {len(all_results)} результатов в Google Sheets...")
        write_results(all_results)
    else:
        logger.warning("Нет результатов для записи")

    # 4. Итог
    success = len(all_results)
    failed = total_links - success
    logger.info(f"\n{'=' * 50}")
    logger.info(f"Готово! Успешно: {success}, Ошибок: {failed}")
    logger.info(f"Дата: {today}")


if __name__ == "__main__":
    run()
