"""Парсинг подписчиков через Apify API."""

from __future__ import annotations

import time
from urllib.parse import urlparse

from apify_client import ApifyClient
from loguru import logger

from config import (
    APIFY_API_TOKEN,
    APIFY_API_TOKEN_BACKUP,
    MAX_RETRIES,
    PLATFORM_ACTORS,
    PLATFORM_NAMES,
    REQUEST_DELAY,
)


def _detect_platform(url: str) -> str | None:
    """Определяет платформу по URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]
    if ":" in domain:
        domain = domain.split(":")[0]

    if domain in PLATFORM_ACTORS:
        return domain

    # pin.it → Pinterest
    if domain == "pin.it":
        return "pinterest.com"

    for key in PLATFORM_ACTORS:
        if key in domain:
            return key

    if "t.me" in domain or "telegram.org" in domain:
        return "t.me"

    return None


def get_platform_name(url: str) -> str:
    """Возвращает человекочитаемое имя платформы."""
    platform_key = _detect_platform(url)
    return PLATFORM_NAMES.get(platform_key, url)


def _get_nested(obj: dict, path: str):
    """Достаёт значение из вложенного словаря по точечной нотации.
    Пример: authorMeta.followers → obj['authorMeta']['followers']"""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _find_followers_in_item(item: dict, field_name: str) -> int | None:
    """Ищет количество подписчиков в item разными способами."""

    # 1. Прямое поле (в т.ч. точечная нотация)
    val = _get_nested(item, field_name)
    if val is not None:
        return int(val)

    # 2. Популярные варианты полей на верхнем уровне
    for variant in [
        "followersCount", "subscribersCount",
        "subscriberCount", "followerCount",
        "fansCount", "totalFollowers",
        "membersCount", "totalMembers",
        "numberOfSubscribers", "subscriber_count",
    ]:
        v = item.get(variant)
        if v is not None:
            return int(v)

    # 3. Для TikTok — authorMeta
    author = item.get("authorMeta", {})
    if isinstance(author, dict):
        for f in ("fans", "followers", "followerCount", "totalFollowers"):
            v = author.get(f)
            if v is not None:
                return int(v)

    # 4. channelStats (YouTube)
    stats = item.get("channelStats", {})
    if isinstance(stats, dict):
        v = stats.get("subscriberCount") or stats.get("totalSubscribers")
        if v is not None:
            return int(v)

    return None


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
        logger.info(f"[{client_name}] Пропуск (нет парсера): {platform_key} ({url})")
        return None

    actor_name = platform_config["actor"]
    field_name = platform_config["field"]

    # Настраиваем input для конкретного актора
    run_input = _build_run_input(actor_name, url, client_name)
    if run_input is None:
        return None

    # Запускаем актор с ретраями
    # Сначала пробуем основной токен, при превышении лимита — резервный
    tokens_to_try = [APIFY_API_TOKEN]
    if APIFY_API_TOKEN_BACKUP:
        tokens_to_try.append(APIFY_API_TOKEN_BACKUP)

    last_error = None
    for token_index, token in enumerate(tokens_to_try):
        if token_index > 0:
            logger.info(f"[{client_name}] Переключаюсь на резервный Apify-токен...")
        client = ApifyClient(token=token)

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                if attempt > 1:
                    logger.info(
                        f"[{client_name}] Попытка #{attempt} для {platform_key}: {url[:60]}..."
                    )
                    time.sleep(REQUEST_DELAY * attempt)

                run = client.actor(actor_name).call(run_input=run_input)
                dataset = client.dataset(run["defaultDatasetId"])
                items = dataset.list_items().items

                if not items:
                    logger.warning(
                        f"[{client_name}] Актор {actor_name} не вернул данных для {url}"
                    )
                    break

                # Ищем количество подписчиков в первом результате
                result = _find_followers_in_item(items[0], field_name)
                if result is not None:
                    logger.info(f"[{client_name}] {platform_key}: {result:,} подписчиков")
                    return result

                # Отладка: покажем ключи ответа
                logger.debug(
                    f"[{client_name}] {actor_name} ответ: keys={list(items[0].keys())[:20]}"
                )
                logger.warning(
                    f"[{client_name}] В ответе {actor_name} нет поля с подписчиками"
                )
                break

            except Exception as e:
                last_error = e
                err_msg = str(e)
                logger.warning(
                    f"[{client_name}] Ошибка попытки #{attempt} для {url}: {err_msg[:120]}"
                )
                # Если лимит исчерпан — не ретраить, сразу fallback
                if "limit exceeded" in err_msg.lower():
                    break
                if attempt <= MAX_RETRIES:
                    continue

    logger.error(
        f"[{client_name}] Все попытки исчерпаны для {url}: {last_error}"
    )
    return None


def _build_run_input(actor_name: str, url: str, client_name: str) -> dict | None:
    """Строит run_input для конкретного Apify актора."""

    if actor_name == "apify/instagram-profile-scraper":
        username = _extract_instagram_username(url)
        if not username:
            logger.warning(f"[{client_name}] Не удалось извлечь username из Instagram: {url}")
            return None
        return {"usernames": [username]}

    if actor_name == "streamers/youtube-scraper":
        return {
            "startUrls": [{"url": url}],
            "maxResults": 10,
            "maxVideos": 10,
            "maxShorts": 0,
            "maxLiveStreams": 0,
        }

    if actor_name == "clockworks/tiktok-profile-scraper":
        username = _extract_tiktok_username(url)
        if not username:
            logger.warning(f"[{client_name}] Не удалось извлечь username из TikTok: {url}")
            return None
        return {"profiles": [username]}

    if actor_name == "apify/facebook-pages-scraper":
        # profile.php — это личные профили, не страницы. Пропускаем.
        if "profile.php" in url:
            logger.info(f"[{client_name}] Пропуск Facebook-профиля (не страница): {url[:60]}...")
            return None
        return {"pageUrls": [url]}

    if actor_name == "easyapi/pinterest-profile-scraper":
        username = _extract_pinterest_username(url)
        if not username:
            logger.warning(f"[{client_name}] Не удалось извлечь username из Pinterest: {url}")
            return None
        return {"usernames": [username]}

    if actor_name == "apify/puppeteer-scraper":
        # Дзен — кастомный pageFunction для Puppeteer
        return {
            "pageFunction": (
                "async function pageFunction(context) {"
                "  const { page, request, log } = context;"
                "  await page.waitForTimeout(3000);"
                "  const result = await page.evaluate(() => {"
                "    const el = document.querySelector('[data-test-id=\"subscribers-count\"]');"
                "    if (el) return { subscribers: parseInt(el.textContent.replace(/[^0-9]/g, '')) };"
                "    const all = document.body.innerText;"
                "    const m = all.match(/(\\d[\\d\\s]*)\\s*(?:подписчик|subscriber| follower)/i);"
                "    if (m) return { subscribers: parseInt(m[1].replace(/\\s/g, '')) };"
                "    return { subscribers: 0, raw: all.slice(0, 500) };"
                "  });"
                "  return result;"
                "}"
            ),
            "startUrls": [{"url": url}],
            "maxPagesPerCrawl": 1,
            "maxResultsPerCrawl": 1,
            "proxyConfiguration": {"useApifyProxy": True},
        }

    if "apify/web-scraper" in actor_name:
        return {
            "pageFunction": (
                "async function pageFunction(context) {"
                '  const $ = context.jQuery;'
                "  return {"
                "    url: context.request.url,"
                "    title: $('title').text()"
                "  };"
                "}"
            ),
            "startUrls": [{"url": url}],
        }

    # Фолбэк
    return {"startUrls": [{"url": url}]}


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


def _extract_pinterest_username(url: str) -> str | None:
    """Извлекает username из Pinterest URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    # Форматы: pinterest.com/username/ или pinterest.com/username/boards/
    parts = path.split("/")
    if parts and parts[0] and parts[0] not in ("pin", "search", "ideas", "business", "_"):
        return parts[0].split("?")[0]
    return None
