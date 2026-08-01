#!/bin/bash

# Переходимо в кореневу папку проекту
cd "$(dirname "$0")"

LOCK_FILE=".last_run_date"
TODAY=$(date +%Y-%m-%d)

# 1. Перевірка: чи запускався скрипт сьогодні
if [ -f "$LOCK_FILE" ]; then
    LAST_RUN=$(cat "$LOCK_FILE")
    if [ "$LAST_RUN" = "$TODAY" ]; then
        echo "⏸️ Скрипт вже виконувався сьогодні ($TODAY). Пропускаємо."
        exit 0
    fi
fi

# 2. Активуємо віртуальне середовище та запускаємо обидва збори
source .venv/bin/activate

echo "🚀 Перший запуск ноута за сьогодні ($TODAY). Збираємо дані..."

python src/ingestion/screentime_ingest.py

# 3. Оновлюємо лок-файл поточним днем, щоб заблокувати повторні запуски
echo "$TODAY" > "$LOCK_FILE"

echo "✨ Усі збори успішно завершено та заблоковано до завтра!"