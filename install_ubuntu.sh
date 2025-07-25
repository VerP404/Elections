#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 manage.py migrate
if [ ! -f db.sqlite3 ]; then
    python3 manage.py migrate
fi
echo "Если нужен суперпользователь, выполните: python3 manage.py createsuperuser"
python3 manage.py runserver 