# Развёртывание парсера на новом сервере

## 1. Клонировать репозиторий

```bash
git clone https://github.com/DEVASTATOR1349/Apify-test-Parcer.git
cd Apify-test-Parcer
```

## 2. Создать `.env` с секретами

```bash
cp .env.example .env
nano .env
```

Заполнить **все** переменные:

```ini
# === Apify ===
APIFY_API_TOKEN=apify_api_...
APIFY_API_TOKEN_BACKUP=apify_api_...

# === Google Sheets ===
SOURCE_SHEET_ID=1j98FzWldWKJmnn22QNuTsraMMwhVMRijemsEOif8RI0
TARGET_SHEET_ID=10S1xijZ4ZNXVB4JQKyBylFmc7N_jwazHKSTc9pNj-t8
APPS_SCRIPT_URL=https://script.google.com/macros/s/AKfycbyRui.../exec

# === Прямые API ===
VK_API_KEY=52508af...
YOUTUBE_API_KEY=AIzaSy...

# === Прокси (для Facebook Playwright) ===
FB_PROXY=http://user:pass@host:port

# === Режим ===
TEST_MODE=false
MAX_RETRIES=2
REQUEST_DELAY_SECONDS=1.5
```

## 3. Собрать и запустить

```bash
docker compose up -d --build
```

Первая сборка займёт 3–5 минут (ставит Chromium для Playwright).

## 4. Проверить что работает

```bash
# Логи контейнера
docker compose logs

# Посмотреть cron-лог
docker compose exec parser cat /app/logs/cron.log

# Запустить вручную
docker compose exec parser /usr/local/bin/python src/main.py
```

## Cron

Запуск: **каждый день в 8:00 МСК** (`0 5 * * *` UTC).

Поменять время можно в `Dockerfile`:
```dockerfile
RUN echo "0 5 * * * cd /app && /usr/local/bin/python src/main.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/parser-cron
```

## Обновление

```bash
git pull
docker compose up -d --build
```

## Что внутри

| Компонент | Зачем |
|---|---|
| `src/main.py` | Точка входа |
| `src/sheets.py` | Чтение «БазаКлиентов» + запись в «ДанныеПарсинга» |
| `src/parser.py` | Диспетчер: native API или Apify |
| `src/native.py` | Прямые парсеры: VK, YouTube, Rutube, OK, Pinterest, Facebook |
| `src/config.py` | Конфигурация платформ и акторов |
| `Dockerfile` | Сборка образа с Playwright + Chromium |
| `docker-entrypoint.sh` | Запуск cron при старте контейнера |

## Примечания

- **Репозиторий публичный** — клонирование по HTTPS без токена
- **Apify**: если основной токен исчерпал лимит, резервный подхватывается автоматически
- **Дзен**: требует одобрения прав актора `puppeteer-scraper` в Apify Console
- **Telegram/Snapchat/Likee/Twitter**: парсеров пока нет
- **Facebook**: Playwright через прокси, ~5–6 секунд на профиль
