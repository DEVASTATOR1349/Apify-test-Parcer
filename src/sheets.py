"""Работа с Google Sheets: чтение через Visualization API, запись через Apps Script.

Все записи идут одним POST-запросом (батч), чтобы не упираться в лимиты Google.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from loguru import logger

from config import APPS_SCRIPT_URL, GOOGLE_SHEET_ID


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
    Читает список проектов и ссылок через Google Visualization API.
    Возвращает [{"name": "Номос", "links": ["https://..."...]}, ...]
    """
    import json

    raw = _fetch_viz_data(gid=0)
    if not raw:
        logger.error("Не удалось получить данные из таблицы")
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return []

    cols = data.get("table", {}).get("cols", [])
    if not cols:
        logger.warning("Нет колонок в таблице")
        return []

    # Парсим заголовки колонок (начиная с 1, т.к. 0 — это дата)
    # Формат: "URL НазваниеПроекта НазваниеПлощадки"
    entries: list[tuple[str, str]] = []
    for i, col in enumerate(cols):
        if i == 0:
            continue
        label = col.get("label", "")
        if not label:
            continue
        parts = label.split(" ")
        url = parts[0]
        if not url.startswith(("http://", "https://")):
            continue
        entries.append((url, " ".join(parts[1:]).strip()))

    # Группируем по проектам
    PLATFORM_NAMES = {
        "Instagram", "Ютуб", "YouTube", "Фейсбук", "Facebook",
        "ТикТок", "TikTok", "ВК", "VK", "Телеграм", "Telegram",
        "Рутьюб", "Rutube", "ОК", "OK",
        "Дзен", "Дзен(Y)", "Пинтерест", "Pinterest", "Лайки",
        "Likee", "Твиттер", "Twitter", "Snapchat",
        "Инст.", "Инст. Самара", "Инстаграм2", "Инстаграм",
        "Лайки(Y)", "Лайки(блок)", "Пинтерст", "Одноклассники",
        "Рутуб", "Рутьюб", "Fb", "IG", "YT", "TT", "tg",
    }

    projects: list[dict[str, Any]] = []
    current_project: str | None = None

    for url, label in entries:
        parts = [p for p in label.split(" ") if p and p != "нету"]
        if not parts:
            continue

        is_new_project = False
        project_name: str | None = None

        if len(parts) >= 2:
            candidate = parts[0]
            if candidate not in PLATFORM_NAMES:
                project_name = candidate
                is_new_project = True
            elif current_project is None:
                project_name = candidate
                is_new_project = True
            else:
                project_name = current_project
        else:
            if current_project:
                project_name = current_project
            else:
                continue

        if is_new_project:
            projects.append({"name": project_name, "links": []})
            current_project = project_name

        if projects:
            projects[-1]["links"].append(url)

    projects = [p for p in projects if p.get("links")]

    logger.info(
        f"Прочитано {len(projects)} проектов, "
        f"всего {sum(len(p['links']) for p in projects)} ссылок"
    )
    for p in projects:
        logger.debug(f"  {p['name']}: {len(p['links'])} ссылок")

    return projects


# ---------------------------------------------------------------------------
# Батч-запись (один POST на всё)
# ---------------------------------------------------------------------------

def write_results(results: list[dict[str, Any]]):
    """Пишет результаты в листы 'Статистика (raw)' + 'Статистика' одним POST."""
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
        "tabs": ["Статистика (raw)", "Статистика"],
        "rows": rows,
    })
    if ok:
        logger.info(f"Батч записан: {len(rows)} строк в 2 листа")
    else:
        logger.error(f"Не удалось записать батч из {len(rows)} строк")


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
