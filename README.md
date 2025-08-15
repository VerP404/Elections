# Elections - Система управления выборами

## Быстрый запуск

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. База данных
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 3. Запуск
```bash
python manage.py runserver 0.0.0.0:9000
```

## Развертывание на сервере

### 1. Клонировать проект
```bash
git clone <URL> Elections
cd Elections
```

### 2. Настроить Python окружение
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Настроить базу данных
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Создать systemd сервис
```bash
# Создать файл /etc/systemd/system/elections.service
sudo nano /etc/systemd/system/elections.service
```

Содержимое файла:
```ini
[Unit]
Description=Elections Django Application
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory=/home/{user}/code/Elections
ExecStart=/home/{user}/Elections/.venv/bin/python start_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Важно:** Заменить `{user}` на имя пользователя (например, `ubuntu`)

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable elections
sudo systemctl start elections
```

### 5. Настроить ежедневный бэкап
```bash
# Создать папку для бэкапов
mkdir -p backups

# Добавить в crontab (crontab -e)
0 0 * * * cd /home/{user}/Elections && source venv/bin/activate && python manage.py dumpdata > backups/db_backup_$(date +\%Y\%m\%d).json
```

## Управление сервисом
```bash
sudo systemctl start elections    # Запустить
sudo systemctl stop elections     # Остановить
sudo systemctl restart elections  # Перезапустить
sudo systemctl status elections   # Статус
```

## Обновление
```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
sudo systemctl restart elections
``` 