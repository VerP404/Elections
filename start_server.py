#!/usr/bin/env python3
"""
Скрипт для запуска Django сервера на порту 9000
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    # Добавляем путь к проекту
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Устанавливаем переменную окружения для Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'elections_system.settings')
    
    # Инициализируем Django
    django.setup()
    
    # Запускаем сервер на порту 9000 и слушаем все IP
    sys.argv = ['manage.py', 'runserver', '0.0.0.0:9000']
    execute_from_command_line(sys.argv)
