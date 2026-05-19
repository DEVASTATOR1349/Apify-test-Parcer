"""Работа с Google Sheets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger

from config import GOOGLE_API_KEY, GOOGLE_SERVICE_ACCOUNT_PATH, GOOGLE_SHEET_ID


def _get_service():
    """Получить сервис Google Sheets."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    if GOOGLE_SERVICE_ACCOUNT_PATH:
        path = Path(GOOGLE_SERVICE_ACCOUNT_PATH)
        if path.exists():
            creds = ServiceCredentials.from_service_account_file(
                str(path), scopes=scopes
            )
            logger.info(f"Авторизация через service account: {path}")
            return build("sheets", "v4", credentials=creds)

        # Возможно путь — это JSON строка, а не файл
        try:
            info = json.loads(GOOGLE_SERVICE_ACCOUNT_PATH)
            creds = ServiceCredentials.from_service_account_info(info, scopes=scopes)
            logger.info("Авторизация через service account (JSON строка)")
            return build("sheets", "v4", credentials=creds)
        except json.JSONDecodeError:
            pass

    if GOOGLE_API_KEY:
        logger.info("Авторизация через API Key")
        return build("sheets", "v4", developerKey=GOOGLE_API_KEY)

    raise ValueError(
        "Не указан GOOGLE_SERVICE_ACCOUNT_JSON или GOOGLE_API_KEY в .env"
    )


def get_sheets_service():
    """Получить инстанс сервиса (кешированный)."""
    if not hasattr(get_sheets_service, "_service"):
        get_sheets_service._service = _get_service()
    return get_sheets_service._service


def read_links_sheet() -> list[dict[str, Any]]:
    """
    Читает лист со ссылками.
    Формат: колонки — [Клиент, Ссылка1, Ссылка2, ..., СсылкаN]
    Первая строка — заголовки.
    """
    service = get_sheets_service()
    sheet = service.spreadsheets()

    # Сначала получим метаданные — все листы
    try:
        metadata = sheet.get(spreadsheetId=GOOGLE_SHEET_ID).execute()
        sheets_meta = metadata.get("sheets", [])

        # Ищем первый лист с данными
        target_tab = None
        for s in sheets_meta:
            title = s["properties"]["title"]
            if title in ("Лист1", "Лист2", "Ссылки", "Clients"):
                target_tab = title
                break

        if not target_tab:
            # Берём первый лист
            target_tab = sheets_meta[0]["properties"]["title"]

        logger.info(f"Читаем лист: {target_tab}")

    except HttpError as e:
        logger.error(f"Ошибка чтения метаданных: {e}")
        return []

    # Читаем все данные с листа
    range_name = f"'{target_tab}'!A:Z"
    try:
        result = sheet.values().get(
            spreadsheetId=GOOGLE_SHEET_ID, range=range_name
        ).execute()
        values = result.get("values", [])
    except HttpError as e:
        logger.error(f"Ошибка чтения листа: {e}")
        return []

    if not values:
        logger.warning("Лист пуст")
        return []

    # Определяем структуру по первой строке
    header = values[0]
    num_cols = len(header)

    # Собираем данные по клиентам
    projects = []
    for row in values[1:]:
        if not row or not row[0]:
            continue

        project_name = str(row[0]).strip()
        if not project_name:
            continue

        links = []
        for col_idx in range(1, min(len(row), num_cols)):
            link = str(row[col_idx]).strip()
            if link and link != "нету" and link.startswith("http"):
                links.append(link)

        if links:
            projects.append({
                "name": project_name,
                "links": links,
            })

    logger.info(f"Найдено проектов: {len(projects)}")
    return projects


def ensure_result_sheets():
    """Создаёт листы для результатов, если их нет."""
    service = get_sheets_service()
    sheet = service.spreadsheets()

    metadata = sheet.get(spreadsheetId=GOOGLE_SHEET_ID).execute()
    existing_tabs = {
        s["properties"]["title"] for s in metadata.get("sheets", [])
    }

    needed_tabs = ["Статистика (raw)", "Ошибки"]
    for tab in needed_tabs:
        if tab not in existing_tabs:
            try:
                request_body = {"requests": [{
                    "addSheet": {"properties": {"title": tab}}
                }]}
                sheet.batchUpdate(
                    spreadsheetId=GOOGLE_SHEET_ID, body=request_body
                ).execute()
                logger.info(f"Создан лист: {tab}")
            except HttpError as e:
                logger.warning(f"Не удалось создать лист {tab}: {e}")


def write_results(results: list[dict[str, Any]]):
    """
    Записывает строчные данные: Дата | Клиент | Площадка | Подписчики
    Дописывает в конец листа Статистика (raw).
    """
    if not results:
        logger.info("Нет данных для записи")
        return

    service = get_sheets_service()
    sheet = service.spreadsheets()

    # Убедимся что листы есть
    ensure_result_sheets()

    range_name = "'Статистика (raw)'!A:D"
    try:
        # Определяем последнюю строку
        existing = sheet.values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_name,
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        existing_values = existing.get("values", [])

        # Если лист пуст — пишем заголовок
        if not existing_values:
            header = [[
                "Дата", "Клиент", "Площадка", "Подписчиков"
            ]]
            sheet.values().update(
                spreadsheetId=GOOGLE_SHEET_ID,
                range="'Статистика (raw)'!A1:D1",
                valueInputOption="RAW",
                body={"values": header},
            ).execute()
            start_row = 2
        else:
            start_row = len(existing_values) + 1

        # Готовим данные
        rows = []
        for r in results:
            rows.append([
                r.get("date", ""),
                r.get("client", ""),
                r.get("platform", ""),
                r.get("followers", ""),
            ])

        # Пишем
        write_range = f"'Статистика (raw)'!A{start_row}:D{start_row + len(rows) - 1}"
        sheet.values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=write_range,
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        logger.info(
            f"Записано {len(rows)} строк в Статистика (raw) начиная со строки {start_row}"
        )

    except HttpError as e:
        logger.error(f"Ошибка записи результатов: {e}")


def log_error(client: str, link: str, error: str):
    """Записывает ошибку в лист Ошибки."""
    from datetime import datetime

    service = get_sheets_service()
    sheet = service.spreadsheets()

    today = datetime.now().strftime("%Y-%m-%d")

    range_name = "'Ошибки'!A:D"
    try:
        existing = sheet.values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_name,
        ).execute()
        vals = existing.get("values", [])

        if not vals:
            sheet.values().update(
                spreadsheetId=GOOGLE_SHEET_ID,
                range="'Ошибки'!A1:D1",
                valueInputOption="RAW",
                body={"values": [["Дата", "Клиент", "Ссылка", "Ошибка"]]},
            ).execute()
            start = 2
        else:
            start = len(vals) + 1

        row = [[today, client, link, error[:200]]]
        sheet.values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"'Ошибки'!A{start}:D",
            valueInputOption="RAW",
            body={"values": row},
        ).execute()

        logger.warning(f"Ошибка записана: {client} / {link} -> {error[:100]}")

    except HttpError as e:
        logger.error(f"Не удалось записать ошибку: {e}")
