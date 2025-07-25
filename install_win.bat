@echo off
python -m venv .venv
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
if not exist db.sqlite3 (
    python manage.py migrate
)
echo Если нужен суперпользователь, выполните: python manage.py createsuperuser
python manage.py runserver 