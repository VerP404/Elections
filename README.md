# Система управления выборами

## Быстрый старт

### 1. Клонируйте репозиторий
```sh
git clone <URL>
cd Elections
```

### 2. Создайте и активируйте виртуальное окружение
#### Windows:
```bat
python -m venv .venv
.venv\Scripts\activate
```
#### Ubuntu:
```sh
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установите зависимости
```sh
pip install -r requirements.txt
```

### 4. Примените миграции
```sh
python manage.py migrate
```

### 5. (Опционально) Создайте суперпользователя
```sh
python manage.py createsuperuser
```

### 6. Запустите сервер
```sh
python manage.py runserver
```

### 7. Откройте в браузере
```
http://127.0.0.1:8000/admin/
```

---

## Быстрая установка скриптом

#### Windows:
```bat
install_win.bat
```
#### Ubuntu:
```sh
bash install_ubuntu.sh
```

---

## Примечания
- Python 3.10+
- Для графиков нужен plotly (`pip install plotly`)
- Для импорта/экспорта — пакет django-import-export
- Все настройки — в `elections_system/settings.py` 