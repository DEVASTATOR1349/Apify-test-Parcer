# Развёртывание парсера на новом сервере

## 1. Клонировать репозиторий

```bash
git clone git@github.com:DEVASTATOR1349/Apify-test-proj---Parcer.git
cd Apify-test-proj---Parcer
```

## 2. Создать `.env` с секретами

```bash
cp .env.example .env
nano .env
```

Заполнить **все** переменные:

```ini
APIFY_API_TOKEN=apify_api_...
APIFY_API_TOKEN_BACKUP=apify_api_...

GOOGLE_SHEET_ID=1j98FzWldWKJmnn22QNuTsraMMwhVMRijemsEOif8RI0
APPS_SCRIPT_URL=https://script.google.com/macros/s/AKfycbyRuiQVTLoXAJP5KvEtYfEzYnI1qbvyRwneTRGIjrAdliNlAuyMn-ftxjTYBGArAOiTOA/exec

VK_API_KEY=52508af...
YOUTUBE_API_KEY=AIzaSy...
FB_PROXY=http://user:pass@host:port

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
docker logs apify-parser

# Запустить вручную (по желанию)
docker exec apify-parser python src/main.py

# Посмотреть cron-лог
docker exec apify-parser cat /app/logs/cron.log
```

## Cron

Запуск: **каждый день в 8:00 МСК** (`0 5 * * *` UTC).

Поменять время можно в `Dockerfile`, строка с `cron`:
```dockerfile
RUN echo "0 5 * * * cd /app && python src/main.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/parser-cron
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
| `src/sheets.py` | Чтение «БазаКлиентов» (gid=21085774) + запись результатов |
| `src/parser.py` | Диспетчер: native API или Apify |
| `src/native.py` | Прямые парсеры: VK, YouTube, Rutube, OK, Pinterest, Facebook (Playwright) |
| `src/config.py` | Конфигурация платформ и акторов |
| `Dockerfile` | Сборка образа с Playwright + Chromium |
| `docker-entrypoint.sh` | Запуск cron при старте контейнера |

## Примечания

- **Apify**: основной токен может исчерпать месячный лимит — резервный подхватывает автоматически
- **Дзен**: требует одобрения прав актора `puppeteer-scraper` в Apify Console
- **Telegram/Snapchat/Likee/Twitter**: парсеров пока нет
- **Facebook**: Playwright через российский прокси, ~5–6 секунд на профиль
