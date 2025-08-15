#!/usr/bin/env python
"""
Скрипт для добавления тестовых данных
"""
import os
import sys
import django
from datetime import date

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'elections_system.settings')
django.setup()

from elections.models import User, UIK, Voter, PlannedVoter, VotingRecord

def add_test_data():
    """Добавление тестовых данных"""
    
    # Получаем существующие объекты
    uik = UIK.objects.get(number=1)
    operator = User.objects.get(username='operator')
    agitator = User.objects.get(username='agitator')
    
    # Создаем тестовых избирателей
    voters_data = [
        {
            'last_name': 'Иванов',
            'first_name': 'Иван',
            'middle_name': 'Иванович',
            'birth_date': date(1980, 5, 15),
            'registration_address': 'г. Москва, ул. Ленина, д. 10, кв. 5',
            'phone_number': '89991234567',
            'uik': uik,
            'created_by': operator
        },
        {
            'last_name': 'Петрова',
            'first_name': 'Анна',
            'middle_name': 'Сергеевна',
            'birth_date': date(1985, 8, 22),
            'registration_address': 'г. Москва, ул. Пушкина, д. 15, кв. 12',
            'phone_number': '89991234568',
            'uik': uik,
            'created_by': operator
        },
        {
            'last_name': 'Сидоров',
            'first_name': 'Петр',
            'middle_name': 'Александрович',
            'birth_date': date(1975, 3, 10),
            'registration_address': 'г. Москва, ул. Гагарина, д. 8, кв. 3',
            'phone_number': '89991234569',
            'uik': uik,
            'created_by': operator
        }
    ]
    
    created_voters = []
    for voter_data in voters_data:
        voter, created = Voter.objects.get_or_create(
            last_name=voter_data['last_name'],
            first_name=voter_data['first_name'],
            middle_name=voter_data['middle_name'],
            birth_date=voter_data['birth_date'],
            defaults=voter_data
        )
        if created:
            print(f"✓ Создан избиратель: {voter.get_full_name()}")
        else:
            print(f"✓ Избиратель уже существует: {voter.get_full_name()}")
        created_voters.append(voter)
    
    # Создаем планируемых избирателей
    for voter in created_voters:
        planned_voter, created = PlannedVoter.objects.get_or_create(
            voter=voter,
            agitator=agitator,
            defaults={
                'planned_date': date(2024, 12, 15),
                'notes': 'Тестовый планируемый избиратель',
                'created_by': operator
            }
        )
        if created:
            print(f"✓ Создан планируемый избиратель: {voter.get_full_name()} -> {agitator.get_full_name()}")
        else:
            print(f"✓ Планируемый избиратель уже существует: {voter.get_full_name()} -> {agitator.get_full_name()}")
    
    print(f"\n🎉 Добавлено {len(created_voters)} избирателей и планируемых избирателей!")
    print(f"УИК: {uik}")
    print(f"Оператор: {operator.get_full_name()}")
    print(f"Агитатор: {agitator.get_full_name()}")

if __name__ == '__main__':
    add_test_data()
