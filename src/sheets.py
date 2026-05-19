"""Работа с Google Sheets: чтение через Visualization API, запись через Apps Script."""

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
        resp = requests.post(APPS_SCRIPT_URL, json=data, timeout=30)
        text = resp.text.strip()
        if resp.status_code == 200 and text == "OK":
            return True
        else:
            logger.warning(f"Apps Script ответил: {resp.status_code} {text[:200]}")
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
    entries = []  # [(url, label)]
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

    # Группируем по проектам.
    # Проект меняется когда после URL идёт >=2 слов и второе слово — это не платформа
    # Эвристика: если в заголовке >=2 частей после URL — это новый проект
    PLATFORM_NAMES = {
        "Instagram", "Ютуб", "YouTube", "Фейсбук", "Facebook",
        "ТикТок", "TikTok", "ВК", "VK", "Телеграм", "Telegram",
        "Рутьюб", "Rutube", "Rutube", "ОК", "OK",
        "Дзен", "Дзен(Y)", "Пинтерест", "Pinterest", "Лайки",
        "Likee", "Твиттер", "Twitter", "Snapchat",
        "Инст.", "Инст. Самара", "Инстаграм2", "Инстаграм",
        "Лайки(Y)", "Лайки(блок)", "Пинтерст", "Одноклассники",
        "Рутуб", "Рутьюб", "Fb", "IG", "YT", "TT", "tg",
    }

    projects = []
    current_project = None

    for url, label in entries:
        parts = [p for p in label.split(" ") if p and p != "нету"]
        if not parts:
            continue

        # Определяем: это новый проект или продолжение?
        is_new_project = False
        project_name = None

        if len(parts) >= 2:
            # Второе слово — потенциальное имя платформы
            # Если это не платформа — значит перед нами многословный проект
            candidate = parts[0]
            second = parts[1]
            if candidate not in PLATFORM_NAMES:
                project_name = candidate
                is_new_project = True
            elif current_project is None:
                # Первая запись — берём как проект
                project_name = candidate
                is_new_project = True
            else:
                # Продолжаем текущий проект
                project_name = current_project
        else:
            # Одно слово после URL — это название площадки (без проекта)
            if current_project:
                project_name = current_project
            else:
                continue

        if is_new_project:
            projects.append({"name": project_name, "links": []})
            current_project = project_name

        # Добавляем ссылку в текущий (последний) проект
        if projects:
            projects[-1]["links"].append(url)

    # Чистка: убираем проекты без ссылок
    projects = [p for p in projects if p.get("links")]

    logger.info(
        f"Прочитано {len(projects)} проектов, "
        f"всего {sum(len(p['links']) for p in projects)} ссылок"
    )
    for p in projects:
        logger.debug(f"  {p['name']}: {len(p['links'])} ссылок")

    return projects


def write_results(results: list[dict[str, Any]]):
    """Пишет результаты в лист Статистика (raw) через Apps Script POST."""
    if not results:
        logger.info("Нет данных для записи")
        return

    success = 0
    for r in results:
        ok = _post({
            "type": "write",
            "tab": "Статистика (raw)",
            "date": r.get("date", ""),
            "client": r.get("client", ""),
            "platform": r.get("platform", ""),
            "followers": str(r.get("followers", "")),
        })
        if ok:
            success += 1

    logger.info(f"Записано строк: {success} из {len(results)}")


def log_error(client: str, link: str, error: str):
    """Пишет ошибку в лист Ошибки."""
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
