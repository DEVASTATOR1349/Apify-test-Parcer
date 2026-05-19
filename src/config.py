"""Конфигурация парсера подписчиков."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Apify ===
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

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
        "actor": "streamers/youtube-scraper",
        "field": "numberOfSubscribers",  # поле на видео (subscriberCount отсутствует)
    },
    "tiktok.com": {
        "actor": "clockworks/tiktok-profile-scraper",
        "field": "authorMeta.fans",  # authorMeta: {fans, following, heart, video}
    },
    "vk.com": {
        "actor": None,  # нет работающего Apify актора (все 404)
        "field": None,
    },
    "facebook.com": {
        "actor": "apify/facebook-pages-scraper",
        "field": "followersCount",
    },
    "ok.ru": {
        "actor": None,  # нет работающего Apify актора
        "field": None,
    },
    "dzen.ru": {
        "actor": "apify/puppeteer-scraper",  # будет заменён на свой актор
        "field": "subscribers",
    },
    "rutube.ru": {
        "actor": None,  # нет работающего Apify актора
        "field": None,
    },
    "t.me": {
        "actor": None,  # нет работающего Apify актора (все 404)
        "field": None,
    },
    "pinterest.com": {
        "actor": "easyapi/pinterest-profile-scraper",
        "field": "followersCount",
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
