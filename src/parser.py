"""Парсинг подписчиков через Apify API."""

from __future__ import annotations

import time
from urllib.parse import urlparse

from apify_client import ApifyClient
from loguru import logger

from config import (
    APIFY_API_TOKEN,
    MAX_RETRIES,
    PLATFORM_ACTORS,
    PLATFORM_NAMES,
    REQUEST_DELAY,
)


def _detect_platform(url: str) -> str | None:
    """Определяет платформу по URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Убираем www
    if domain.startswith("www."):
        domain = domain[4:]
    # Убираем порт если есть
    if ":" in domain:
        domain = domain.split(":")[0]

    # Проверяем точное совпадение
    if domain in PLATFORM_ACTORS:
        return domain

    # Проверяем вхождение
    for key in PLATFORM_ACTORS:
        if key in domain:
            return key

    # Telegram может быть t.me или web.telegram.org
    if "t.me" in domain or "telegram.org" in domain:
        return "t.me"

    return None


def get_platform_name(url: str) -> str:
    """Возвращает человекочитаемое имя платформы."""
    platform_key = _detect_platform(url)
    return PLATFORM_NAMES.get(platform_key, url)


def fetch_followers(url: str, client_name: str) -> int | None:
    """
    Получает количество подписчиков для одной ссылки через Apify.

    Returns:
        int — количество подписчиков
        None — если не удалось получить
    """
    platform_key = _detect_platform(url)
    if not platform_key:
        logger.warning(f"[{client_name}] Неизвестная платформа: {url}")
        return None

    platform_config = PLATFORM_ACTORS.get(platform_key)
    if platform_config is None or platform_config.get("actor") is None:
        logger.info(f"[{client_name}] Платформа без парсера: {platform_key} ({url})")
        return None

    actor_name = platform_config["actor"]
    field_name = platform_config["field"]

    # Настраиваем input для конкретного актора
    if actor_name == "apify/web-scraper":
        # Универсальный веб-скрейпер — настраиваем под конкретный сайт
        run_input = {
            "pageFunction": (
                "async function pageFunction(context) {"
                "  const $ = context.jQuery;"
                "  return {"
                "    url: context.request.url,"
                "    title: $('title').text()"
                "  };"
                "}"
            ),
            "startUrls": [{"url": url}],
        }
    elif actor_name == "apify/instagram-profile-scraper":
        username = _extract_instagram_username(url)
        if not username:
            logger.warning(f"[{client_name}] Не удалось извлечь username из Instagram: {url}")
            return None
        run_input = {"usernames": [username]}
    elif actor_name == "apify/youtube-scraper":
        run_input = {"channelUrls": [url]}
    elif actor_name in ("apify/twitter-scraper", "apify/twitter-profile-scraper"):
        run_input = {"urls": [url]}
    elif actor_name == "clockworks/tiktok-profile-scraper":
        username = _extract_tiktok_username(url)
        if not username:
            logger.warning(f"[{client_name}] Не удалось извлечь username из TikTok: {url}")
            return None
        run_input = {"username": [username]}
    elif actor_name == "apify/vk-community-stats":
        screen_name = _extract_vk_screenname(url)
        if not screen_name:
            logger.warning(f"[{client_name}] Не удалось извлечь screen_name из VK: {url}")
            return None
        run_input = {"screenName": screen_name}
    elif actor_name == "apify/facebook-pages-scraper":
        run_input = {"pageUrls": [url]}
    elif actor_name == "apify/telegram-channel-scraper":
        username = _extract_telegram_username(url)
        if not username:
            logger.warning(f"[{client_name}] Не удалось извлечь username из Telegram: {url}")
            return None
        run_input = {"channelUsername": username}
    elif actor_name == "apify/odnoklassniki-scraper":
        run_input = {"groupUrls": [url]}
    elif actor_name == "apify/pinterest-scraper":
        run_input = {"profileUrls": [url]}
    else:
        run_input = {"startUrls": [{"url": url}]}

    # Запускаем актор с ретраями
    client = ApifyClient(token=APIFY_API_TOKEN)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 2):  # +2 потому что MAX_RETRIES — это повторы
        try:
            if attempt > 1:
                logger.info(
                    f"[{client_name}] Попытка #{attempt} для {platform_key}: {url[:60]}..."
                )
                time.sleep(REQUEST_DELAY * attempt)

            # Запускаем актор
            run = client.actor(actor_name).call(run_input=run_input)

            # Ждём результат
            dataset = client.dataset(run["defaultDatasetId"])
            items = dataset.list_items().items

            if not items:
                logger.warning(
                    f"[{client_name}] Актор {actor_name} не вернул данных для {url}"
                )
                return None

            # Ищем нужное поле
            for item in items:
                # Пробуем разные варианты названий полей
                for key_variant in [field_name, "followersCount", "subscribersCount",
                                    "subscriberCount", "followerCount",
                                    "fansCount", "totalFollowers",
                                    "membersCount", "totalMembers"]:
                    val = item.get(key_variant)
                    if val is not None:
                        return int(val)

                # Если не нашли — возьмём первое числовое поле
                for key, val in item.items():
                    if isinstance(val, (int, float)) and val > 0:
                        return int(val)

            # Ничего не нашли
            logger.warning(
                f"[{client_name}] В ответе {actor_name} нет поля {field_name}"
            )
            return None

        except Exception as e:
            last_error = e
            logger.warning(
                f"[{client_name}] Ошибка попытки #{attempt} для {url}: {e}"
            )
            if attempt <= MAX_RETRIES + 1:
                continue

    logger.error(
        f"[{client_name}] Все попытки исчерпаны для {url}: {last_error}"
    )
    return None


def _extract_instagram_username(url: str) -> str | None:
    """Извлекает username из Instagram URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    if parts and parts[0]:
        return parts[0].split("?")[0]
    return None


def _extract_tiktok_username(url: str) -> str | None:
    """Извлекает username из TikTok URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    for part in parts:
        if part.startswith("@"):
            return part[1:].split("?")[0]
    return None


def _extract_vk_screenname(url: str) -> str | None:
    """Извлекает screen_name из VK URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    if parts and parts[0]:
        return parts[0]
    return None


def _extract_telegram_username(url: str) -> str | None:
    """Извлекает username из Telegram URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    # Убираем префикс #
    for part in parts:
        clean = part.lstrip("#")
        if clean and clean != "k":
            return clean.split("?")[0]
    return None
