# apify-parser
# Парсер подписчиков через Apify → Google Sheets

## Установка

```bash
cd /path/to/apify-parser
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактируй .env — вставь токены
```

## Запуск

```bash
# Разовый прогон
source venv/bin/activate
python src/main.py

# Или через cron (см. crontab.example)
crontab crontab.example
```

## Логи

Логи пишутся в `logs/parser_YYYY-MM-DD.log`. Авто-ротация раз в 30 дней.

## Как это работает

1. Читает Google Sheets — список проектов и ссылки на соцсети
2. Для каждой ссылки определяет платформу
3. Через Apify API запускает нужный актор
4. Ждёт результат, извлекает количество подписчиков
5. Пишет в лист "Статистика (raw)" в формате: Дата | Клиент | Площадка | Подписчиков
6. Ошибки пишет в лист "Ошибки"

## Лимиты

- Макс 2 повторных запроса при ошибке
- Задержка 1.5с между запросами
```
