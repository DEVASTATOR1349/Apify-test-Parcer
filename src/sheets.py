"""Работа с Google Sheets: чтение через Visualization API, запись через Apps Script.

Все записи идут одним POST-запросом (батч), чтобы не упираться в лимиты Google.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from loguru import logger

from config import APPS_SCRIPT_URL, SOURCE_SHEET_ID, SHEET_LINKS_GID, SOURCE_NAME_MAP


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
        f"https://docs.google.com/spreadsheets/d/{SOURCE_SHEET_ID}"
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


# ---------------------------------------------------------------------------
# Чтение «БазыКлиентов»
# ---------------------------------------------------------------------------

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

    projects: dict[str, list[str]] = {}
    skipped_sources: set[str] = set()

    for row in rows[1:]:
        vals = [c.get("v") if c else None for c in row["c"]]
        client = (vals[0] or "").strip()
        source = (vals[1] or "").strip()
        url = (vals[2] or "").strip()

        if not client or not url:
            continue
        if not url.startswith(("http://", "https://")):
            continue

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
# Батч-запись результатов
# ---------------------------------------------------------------------------

def write_results(results: list[dict[str, Any]]):
    """Пишет результаты в лист «Статистика SQL» (Дата, Клиент, Площадка, Подписчиков)."""
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
    ok = _post({"type": "batch_write", "rows": rows, "tab": "Статистика новая"})
    if ok:
        logger.info(f"Записано: {len(rows)} строк в «Статистика новая»")
    else:
        logger.error(f"Не удалось записать {len(rows)} строк")


def log_errors_batch(errors: list[dict[str, str]]):
    """Пишет ошибки одним POST в лист «Ошибки»."""
    if not errors:
        return
    ok = _post({
        "type": "batch_errors",
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
# Старый интерфейс (для совместимости)
# ---------------------------------------------------------------------------

def log_error(client: str, link: str, error: str):
    """Однострочная запись ошибки."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _post({
        "type": "error",
        "date": today,
        "client": client,
        "link": link,
        "error": error[:200],
    })
    logger.warning(f"Ошибка записана: {client} / {error[:100]}")
