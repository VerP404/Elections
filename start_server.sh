#!/bin/bash

# Лог-файл с временной меткой
LOG_FILE="/tmp/elections_runserver_$(date +'%Y%m%d_%H%M%S').log"

echo "=============================================="
echo "Запуск Django-сервера: $(date)"
echo "Лог: $LOG_FILE"
echo "=============================================="

# Переход в директорию скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo "[ERROR] Не удалось перейти в директорию!"; exit 1; }

# Активация виртуального окружения
echo "[INFO] Активация виртуального окружения..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Не удалось активировать виртуальное окружение!"
    exit 1
fi

# Остановка старого процесса Django
echo "[INFO] Остановка старого процесса Django (runserver)..."
pkill -f 'manage.py runserver'
echo "[INFO] Старый процесс Django остановлен (если был запущен)."

# Запуск нового процесса Django на порту 5090
echo "[INFO] Запуск Django на порту 5090..."
nohup python manage.py runserver 0.0.0.0:5090 > "$LOG_FILE" 2>&1 &

echo "[INFO] Сервер запущен на http://0.0.0.0:5090/ (доступен с других устройств в сети)"
echo "[INFO] Для локального доступа: http://127.0.0.1:5090/"
echo "==============================================" 