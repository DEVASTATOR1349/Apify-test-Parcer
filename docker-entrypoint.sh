#!/bin/bash
set -e

echo "=== Парсер подписчиков ==="
echo "Дата: $(date -u)"

# Делаем разовый прогон при старте
echo "→ Выполняю первичный прогон..."
cd /app
python src/main.py

echo "→ Запускаю cron в фоне..."
# Запускаем cron
cron

# Держим контейнер живым
touch /app/logs/cron.log
tail -f /app/logs/cron.log
