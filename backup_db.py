#!/usr/bin/env python3
"""
Скрипт для создания бэкапа базы данных
"""

import os
import sys
import django
from datetime import datetime

if __name__ == '__main__':
    # Добавляем путь к проекту
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Устанавливаем переменную окружения для Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'elections_system.settings')
    
    # Инициализируем Django
    django.setup()
    
    # Создаем папку для бэкапов если её нет
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Создаем имя файла с датой
    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'db_backup_{date_str}.json')
    
    # Создаем бэкап
    from django.core.management import call_command
    
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            call_command('dumpdata', stdout=f, indent=2)
        print(f'Бэкап создан: {backup_file}')
    except Exception as e:
        print(f'Ошибка создания бэкапа: {e}')
        sys.exit(1)
