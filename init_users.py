#!/usr/bin/env python
"""
Скрипт инициализации для создания тестовых пользователей
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'elections_system.settings')
django.setup()

from django.contrib.auth import get_user_model
from elections.models import User, UIK, Workplace

def create_test_users():
    """Создание тестовых пользователей"""
    
    # Создаем место работы
    workplace, created = Workplace.objects.get_or_create(
        name='БУЗ ВО "ВГКП №3"',
        defaults={'name': 'БУЗ ВО "ВГКП №3"'}
    )
    if created:
        print(f"✓ Создано место работы: {workplace.name}")
    
    # Создаем суперпользователя
    if not User.objects.filter(username='admin').exists():
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='Qaz123',
            first_name='Дмитрий',
            last_name='Солнцев',
            middle_name='Александрович',
            phone_number='89525540000',
            role='admin',
            workplace=workplace
        )
        print(f"✓ Создан суперпользователь: {admin_user.username}")
    else:
        print("✓ Суперпользователь admin уже существует")

    if not User.objects.filter(username='solncev').exists():
        admin_user = User.objects.create_superuser(
            username='solncev',
            email='solncev@example.com',
            password='Qaz123',
            first_name='Администратор',
            last_name='Системы',
            middle_name='Администраторович',
            phone_number='89999999999',
            role='admin',
            workplace=workplace
        )
        print(f"✓ Создан суперпользователь: {admin_user.username}")
    else:
        print("✓ Суперпользователь admin уже существует")
    # Создаем бригадира
    if not User.objects.filter(username='brigadier').exists():
        brigadier = User.objects.create_user(
            username='brigadier',
            email='brigadier@example.com',
            password='Qaz123',
            first_name='Бригадир',
            last_name='Тестовый',
            middle_name='Бригадирович',
            phone_number='89999999998',
            role='brigadier',
            workplace=workplace,
            is_staff=True
        )
        print(f"✓ Создан бригадир: {brigadier.username}")
    else:
        print("✓ Бригадир brigadier уже существует")
    
    # Создаем агитатора
    if not User.objects.filter(username='agitator').exists():
        agitator = User.objects.create_user(
            username='agitator',
            email='agitator@example.com',
            password='Qaz123',
            first_name='Агитатор',
            last_name='Тестовый',
            middle_name='Агитаторович',
            phone_number='89999999997',
            role='agitator',
            workplace=workplace,
            is_staff=True
        )
        print(f"✓ Создан агитатор: {agitator.username}")
    else:
        print("✓ Агитатор agitator уже существует")
    
    # Создаем оператора
    if not User.objects.filter(username='operator').exists():
        operator = User.objects.create_user(
            username='operator',
            email='operator@example.com',
            password='Qaz123',
            first_name='Оператор',
            last_name='Тестовый',
            middle_name='Операторович',
            phone_number='89999999996',
            role='operator',
            workplace=workplace,
            is_staff=True
        )
        print(f"✓ Создан оператор: {operator.username}")
    else:
        print("✓ Оператор operator уже существует")
    
    print("\n🎉 Инициализация завершена!")
    print("\nДанные для входа:")
    print("admin / Qaz123 - Суперпользователь")
    print("brigadier / Qaz123 - Бригадир")
    print("agitator / Qaz123 - Агитатор")
    print("operator / Qaz123 - Оператор")

if __name__ == '__main__':
    create_test_users()
