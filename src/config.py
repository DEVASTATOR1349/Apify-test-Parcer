"""Конфигурация парсера подписчиков."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Apify ===
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_API_TOKEN_BACKUP = os.getenv("APIFY_API_TOKEN_BACKUP")

# === Прямые API ===
VK_API_KEY = os.getenv("VK_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# === Режим ===
TEST_MODE = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")

# === Apps Script (Google Sheets bridge) ===
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# === Парсер ===
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", "1.5"))

# === Листы в Google Sheets ===
# Лист со списком клиентов и ссылок (Лист1 / первый лист)
SHEET_LINKS_TAB = "Лист1"
# Лист куда пишем строчные данные (создадим если нет)
SHEET_RESULTS_TAB = "Статистика (raw)"
# Лист для лога ошибок
SHEET_ERRORS_TAB = "Ошибки"

# === Маппинг доменов к Apify акторам ===
PLATFORM_ACTORS = {
    "instagram.com": {
        "actor": "apify/instagram-profile-scraper",
        "field": "followersCount",
    },
    "youtube.com": {
        "actor": "native",  # YouTube Data API v3
        "field": "statistics.subscriberCount",
    },
    "tiktok.com": {
        "actor": "clockworks/tiktok-profile-scraper",
        "field": "authorMeta.fans",  # Apify
    },
    "vk.com": {
        "actor": "native",  # VK API
        "field": "members_count",
    },
    "facebook.com": {
        "actor": "apify/facebook-pages-scraper",
        "field": "followersCount",
    },
    "ok.ru": {
        "actor": "native",  # парсинг HTML
        "field": "membersCount",
    },
    "dzen.ru": {
        "actor": "apify/puppeteer-scraper",  # будет заменён на свой актор
        "field": "subscribers",
    },
    "rutube.ru": {
        "actor": "native",  # /api/video/person/
        "field": "subscribers_count",
    },
    "t.me": {
        "actor": None,  # нет работающего Apify актора (все 404)
        "field": None,
    },
    "pinterest.com": {
        "actor": "native",  # JSON-LD парсинг
        "field": "followerCount",
    },
    "x.com":
    {
        "actor": None,  # нет работающего Apify актора
        "field": None,
    },
    "twitter.com": {
        "actor": None,  # нет работающего Apify актора
        "field": None,
    },
    "snapchat.com": {
        "actor": None,  # Snapchat пока не парсим
        "field": None,
    },
    "likee.video": {
        "actor": None,  # нет работающего Apify актора
        "field": None,
    },
}

# Названия площадок для человекочитаемого вывода
PLATFORM_NAMES = {
    "instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "tiktok.com": "TikTok",
    "vk.com": "VK",
    "facebook.com": "Facebook",
    "ok.ru": "OK",
    "dzen.ru": "Дзен",
    "rutube.ru": "Rutube",
    "t.me": "Telegram",
    "pinterest.com": "Pinterest",
    "x.com": "Twitter",
    "twitter.com": "Twitter",
    "snapchat.com": "Snapchat",
    "likee.video": "Likee",
}
