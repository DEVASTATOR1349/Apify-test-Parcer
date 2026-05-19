"""Работа с Google Sheets: чтение через Visualization API, запись через Apps Script.

Все записи идут одним POST-запросом (батч), чтобы не упираться в лимиты Google.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from loguru import logger

from urllib.parse import urlparse, urlunparse

from config import APPS_SCRIPT_URL, GOOGLE_SHEET_ID, SHEET_LINKS_GID, SOURCE_NAME_MAP


def _post(data: dict) -> bool:
    """Отправляет POST в Apps Script."""
    if not APPS_SCRIPT_URL:
        logger.error("APPS_SCRIPT_URL не задан!")
        return False

    try:
        resp = requests.post(
            APPS_SCRIPT_URL, json=data, timeout=60
        )
        text = resp.text.strip()
        if resp.status_code == 200 and text == "OK":
            return True
        else:
            logger.warning(
                f"Apps Script ответил: {resp.status_code} {text[:200]}"
            )
            return False
    except requests.RequestException as e:
        logger.error(f"Ошибка отправки в Apps Script: {e}")
        return False


def _fetch_viz_data(gid: int = 0) -> dict | None:
    """Читает данные через Google Visualization API (работает без авторизации)."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"
        f"/gviz/tq?tqx=out:json&gid={gid}"
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.text

        marker = "google.visualization.Query.setResponse("
        start = content.index(marker) + len(marker)
        end = content.rindex(")")
        return content[start:end] if marker in content else None
    except Exception as e:
        logger.warning(f"Visualization API error: {e}")
        return None


def read_links_sheet() -> list[dict[str, Any]]:
    """
    Читает «БазуКлиентов» (gid=21085774) через Google Visualization API.
    Формат: 3 колонки — Клиент, Источник, ссылка.
    Возвращает [{"name": "ВсеСвои", "links": ["https://...", ...]}, ...]
    """
    import json

    raw = _fetch_viz_data(gid=SHEET_LINKS_GID)
    if not raw:
        logger.error("Не удалось получить данные из таблицы (БазаКлиентов)")
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return []

    rows = data.get("table", {}).get("rows", [])
    if not rows:
        logger.warning("Нет данных в «БазеКлиентов»")
        return []

    # Группируем: Клиент → [ссылки]
    projects: dict[str, list[str]] = {}
    skipped_sources: set[str] = set()

    for row in rows[1:]:  # пропускаем заголовок
        vals = [c.get("v") if c else None for c in row["c"]]
        client = (vals[0] or "").strip()
        source = (vals[1] or "").strip()
        url = (vals[2] or "").strip()

        if not client or not url:
            continue
        if not url.startswith(("http://", "https://")):
            continue

        # Проверяем что источник — известная платформа
        platform_key = SOURCE_NAME_MAP.get(source)
        if not platform_key:
            skipped_sources.add(source)
            continue

        if client not in projects:
            projects[client] = []
        projects[client].append(url)

    if skipped_sources:
        logger.debug(f"Пропущенные источники: {', '.join(sorted(skipped_sources))}")

    result = [{"name": k, "links": v} for k, v in projects.items()]
    logger.info(
        f"«БазаКлиентов»: {len(result)} проектов, "
        f"всего {sum(len(p['links']) for p in result)} ссылок"
    )
    for p in result:
        logger.debug(f"  {p['name']}: {len(p['links'])} ссылок")

    return result


# ---------------------------------------------------------------------------
# Батч-запись (один POST на всё)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# URL-нормализация и маппинг колонок «Статистики»
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """
    Нормализует URL для сопоставления.
    - нижний регистр
    - http → https
    - убирает www.
    - убирает query-параметры и fragment
    - убирает trailing slash
    """
    parsed = urlparse(url.lower())
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    # Всегда https для единообразия (на http редиректит)
    return urlunparse(("https", netloc, path, "", "", ""))


def build_stats_columns() -> dict[str, int]:
    """
    Читает заголовки листа «Статистика» (gid=0) и строит карту
    {нормализованный_URL → индекс_колонки (0-based, как в Google Sheets)}.
    """
    import json

    raw = _fetch_viz_data(gid=0)
    if not raw:
        logger.error("Не удалось прочитать Статистику")
        return {}

    data = json.loads(raw)
    cols = data.get("table", {}).get("cols", [])

    col_map: dict[str, int] = {}
    skipped = 0
    for i, col in enumerate(cols):
        label = col.get("label", "")
        if not label:
            skipped += 1
            continue
        # Первый токен — URL
        parts = label.split(" ")
        url = parts[0]
        if not url.startswith(("http://", "https://")):
            skipped += 1
            continue
        key = normalize_url(url)
        if key:
            col_map[key] = i

    logger.info(f"Колонок Статистики: {len(cols)}, сопоставлено URL: {len(col_map)}, пропущено: {skipped}")
    return col_map


# ---------------------------------------------------------------------------
# Батч-запись (один POST на всё)
# ---------------------------------------------------------------------------

def write_results(results: list[dict[str, Any]]):
    """Пишет результаты в лист «Статистика (raw)» плоскими строками."""
    if not results:
        logger.info("Нет данных для записи")
        return

    rows = [
        [
            r.get("date", ""),
            r.get("client", ""),
            r.get("platform", ""),
            str(r.get("followers", "")),
        ]
        for r in results
    ]
    ok = _post({
        "type": "batch_write",
        "tabs": ["Статистика (raw)"],
        "rows": rows,
    })
    if ok:
        logger.info(f"Батч записан: {len(rows)} строк в «Статистика (raw)»")
    else:
        logger.error(f"Не удалось записать батч из {len(rows)} строк")


def write_stats_matrix(date: str, column_fills: list[tuple[int, int]]):
    """
    Пишет значения в лист «Статистика» (матрица: колонка = площадка, строка = дата).
    column_fills: [(col_index, followers_value), ...]
    """
    if not column_fills:
        return

    ok = _post({
        "type": "matrix_write",
        "tab": "Статистика",
        "date": date,
        "cells": [[ci, fv] for ci, fv in column_fills],
    })
    if ok:
        logger.info(f"Матрица записана: {len(column_fills)} ячеек в «Статистику»")
    else:
        logger.error(f"Не удалось записать матрицу ({len(column_fills)} ячеек)")


def log_errors_batch(errors: list[dict[str, str]]):
    """Пишет все ошибки одним POST в лист 'Ошибки'."""
    if not errors:
        return
    ok = _post({
        "type": "batch_errors",
        "tab": "Ошибки",
        "rows": [
            [e["date"], e["client"], e["link"], e["error"]]
            for e in errors
        ],
    })
    if ok:
        logger.info(f"Записано ошибок: {len(errors)}")
    else:
        logger.warning(f"Не удалось записать {len(errors)} ошибок")


# ---------------------------------------------------------------------------
# Старый интерфейс (оставлен для обратной совместимости)
# ---------------------------------------------------------------------------

def log_error(client: str, link: str, error: str):
    """Однострочная запись ошибки (используй log_errors_batch для массовой)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _post({
        "type": "error",
        "date": today,
        "client": client,
        "link": link,
        "error": error[:200],
    })
    logger.warning(f"Ошибка записана: {client} / {error[:100]}")


def ensure_result_sheets():
    """Проверяет создание листов (через тестовую запись)."""
    _post({
        "type": "write",
        "tab": "Статистика (raw)",
        "date": "__init__",
        "client": "__init__",
        "platform": "__init__",
        "followers": "__init__",
    })
    logger.info("Инициализация листов выполнена")
