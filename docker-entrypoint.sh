#!/bin/bash
set -e

echo "=== Парсер подписчиков ==="
echo "Дата: $(date -u)"
echo "Cron настроен на 5:00 UTC (8:00 МСК) ежедневно"
echo ""

# Запускаем cron
cron

# Держим контейнер живым
touch /app/logs/cron.log
tail -f /app/logs/cron.log
