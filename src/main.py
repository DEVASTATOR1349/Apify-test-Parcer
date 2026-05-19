"""Точка входа парсера подписчиков.

TEST_MODE=true → по 1 ссылке на каждую платформу (не жрёт Apify).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from loguru import logger

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

from config import TEST_MODE
from sheets import read_links_sheet, write_results, write_stats_matrix, log_errors_batch, normalize_url, build_stats_columns
from parser import fetch_followers, get_platform_name, _detect_platform


def run():
    logger.info("=" * 50)
    logger.info("Запуск парсера подписчиков" + (" [ТЕСТОВЫЙ РЕЖИМ]" if TEST_MODE else ""))

    projects = read_links_sheet()
    if not projects:
        logger.warning("Нет проектов для парсинга")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if TEST_MODE:
        _run_test(projects, today)
    else:
        _run_full(projects, today)


def _run_test(projects, today):
    """Тестовый режим: по 1 ссылке на каждую уникальную платформу."""
    logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ: по 1 проверке на платформу\n")

    seen_platforms = {}
    for project in projects:
        for link in project["links"]:
            pk = _detect_platform(link)
            if pk and pk not in seen_platforms:
                seen_platforms[pk] = (project["name"], link)

    logger.info(f"Платформ для теста: {len(seen_platforms)}")
    all_results = []
    all_errors = []

    for pk, (client, link) in seen_platforms.items():
        platform_name = get_platform_name(link)
        logger.info(f"[тест] {client} → {platform_name} ({pk})")
        followers = fetch_followers(link, client)
        if followers is not None:
            all_results.append({
                "date": today, "client": client,
                "platform": platform_name, "followers": str(followers),
            })
            logger.success(f"  ✅ {platform_name}: {followers} подписчиков")
        else:
            all_errors.append({
                "date": today, "client": client,
                "link": link, "error": "Не удалось получить подписчиков",
            })
            logger.warning(f"  ❌ {platform_name}: не удалось")

    if all_errors:
        log_errors_batch(all_errors)
    if all_results:
        logger.info(f"\nЗапись {len(all_results)} результатов...")
        write_results(all_results)

    logger.info(f"\n{'=' * 50}")
    logger.info(f"Тест завершён! Успешно: {len(all_results)}, Ошибок: {len(all_errors)}")


def _run_full(projects, today):
    """Полный прогон по всем ссылкам."""
    all_results = []
    all_errors = []
    total_links = sum(len(p["links"]) for p in projects)
    logger.info(f"Проектов: {len(projects)}, ссылок: {total_links}")

    # Строим карту URL → колонка в Статистике
    col_map = build_stats_columns()
    if not col_map:
        logger.warning("Не удалось прочитать колонки Статистики, пишу только в (raw)")
    else:
        logger.info(f"Карта колонок: {len(col_map)} URL")

    stats_fills: list[tuple[int, int]] = []  # (col_index, followers)
    not_matched_urls: set[str] = set()

    processed = 0
    for project in projects:
        name = project["name"]
        links = project["links"]
        logger.info(f"\n--- {name} ({len(links)} площадок) ---")

        for link in links:
            processed += 1
            logger.info(f"[{processed}/{total_links}] {name} → {link[:70]}...")
            platform_name = get_platform_name(link)
            followers = fetch_followers(link, name)

            if followers is not None:
                all_results.append({
                    "date": today, "client": name,
                    "platform": platform_name, "followers": str(followers),
                })

                # Сопоставляем URL → колонка Статистики
                norm = normalize_url(link)
                if norm in col_map:
                    stats_fills.append((col_map[norm], followers))
                    logger.debug(f"  → колонка {col_map[norm]}")
                else:
                    not_matched_urls.add(norm)
                    logger.debug(f"  ⚠ URL не найден в Статистике: {norm}")

                logger.success(f"  ✅ {platform_name}: {followers} подписчиков")
            else:
                all_errors.append({
                    "date": today, "client": name,
                    "link": link, "error": "Не удалось получить подписчиков",
                })

    if not_matched_urls:
        logger.warning(
            f"{len(not_matched_urls)} URL не сопоставлены с колонками Статистики: "
            f"{', '.join(sorted(not_matched_urls)[:10])}"
        )

    # Пишем
    if all_errors:
        log_errors_batch(all_errors)
    if all_results:
        write_results(all_results)
    if stats_fills:
        write_stats_matrix(today, stats_fills)
    elif col_map:
        logger.warning("Нет данных для матрицы Статистики")

    success = len(all_results)
    logger.info(f"\n{'=' * 50}")
    logger.info(f"Готово! Успешно: {success}, матрица: {len(stats_fills)} ячеек, Ошибок: {total_links - success}")


if __name__ == "__main__":
    run()
