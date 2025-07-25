#!/usr/bin/env python
"""
Скрипт для создания базовых групп пользователей с правами
"""

import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'elections_system.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

def create_groups_with_permissions():
    """Создание базовых групп с правами"""
    
    print("🔧 Создание групп пользователей...")
    
    # Получаем типы контента для наших моделей
    from elections.models import User, UIK, Workplace, Participant, Voter, UIKResults, Analytics
    
    # 1. Администраторы данных - полные права на справочники
    admin_group, created = Group.objects.get_or_create(name='Администраторы данных')
    if created:
        print("✅ Создана группа: Администраторы данных")
        
        admin_permissions = [
            # УИК
            'elections.view_uik', 'elections.add_uik', 'elections.change_uik', 'elections.delete_uik',
            # Места работы
            'elections.view_workplace', 'elections.add_workplace', 'elections.change_workplace', 'elections.delete_workplace',
            # Участники
            'elections.view_participant', 'elections.add_participant', 'elections.change_participant', 'elections.delete_participant',
        ]
        
        permissions = Permission.objects.filter(codename__in=[p.split('.')[1] for p in admin_permissions])
        admin_group.permissions.set(permissions)
        print(f"   Назначено {permissions.count()} разрешений")
    
    # 2. Операторы избирателей - работа с избирателями
    operators_group, created = Group.objects.get_or_create(name='Операторы избирателей')
    if created:
        print("✅ Создана группа: Операторы избирателей")
        
        operator_permissions = [
            # Избиратели
            'elections.view_voter', 'elections.add_voter', 'elections.change_voter',
            # Просмотр справочников для выбора
            'elections.view_uik', 'elections.view_workplace', 'elections.view_participant',
        ]
        
        permissions = Permission.objects.filter(codename__in=[p.split('.')[1] for p in operator_permissions])
        operators_group.permissions.set(permissions)
        print(f"   Назначено {permissions.count()} разрешений")
    
    # 3. Аналитики - просмотр результатов и создание аналитики
    analysts_group, created = Group.objects.get_or_create(name='Аналитики')
    if created:
        print("✅ Создана группа: Аналитики")
        
        analyst_permissions = [
            # Результаты УИК
            'elections.view_uikresults', 'elections.change_uikresults',
            # Аналитика
            'elections.view_analytics', 'elections.add_analytics', 'elections.change_analytics',
            # Просмотр для анализа
            'elections.view_voter', 'elections.view_uik', 'elections.view_participant',
        ]
        
        permissions = Permission.objects.filter(codename__in=[p.split('.')[1] for p in analyst_permissions])
        analysts_group.permissions.set(permissions)
        print(f"   Назначено {permissions.count()} разрешений")
    
    # 4. Только просмотр - все видят, ничего не меняют
    viewers_group, created = Group.objects.get_or_create(name='Только просмотр')
    if created:
        print("✅ Создана группа: Только просмотр")
        
        viewer_permissions = [
            # Только просмотр всего
            'elections.view_voter', 'elections.view_uik', 'elections.view_workplace', 
            'elections.view_participant', 'elections.view_uikresults', 'elections.view_analytics'
        ]
        
        permissions = Permission.objects.filter(codename__in=[p.split('.')[1] for p in viewer_permissions])
        viewers_group.permissions.set(permissions)
        print(f"   Назначено {permissions.count()} разрешений")
    
    print("\n🎉 Все группы успешно созданы!")
    print("\n📋 Созданные группы:")
    print("1. 'Администраторы данных' - управление справочниками")
    print("2. 'Операторы избирателей' - работа с избирателями")
    print("3. 'Аналитики' - результаты и аналитика")
    print("4. 'Только просмотр' - просмотр без изменений")
    print("\n💡 Теперь назначьте пользователей в группы через админку!")

if __name__ == '__main__':
    create_groups_with_permissions() 