from django.core.management.base import BaseCommand
from django.http import HttpResponse
from import_export.formats.base_formats import XLSX
from elections.admin import UserResource
from elections.models import User
import io


class Command(BaseCommand):
    help = 'Генерирует шаблон Excel для импорта пользователей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='user_import_template.xlsx',
            help='Имя выходного файла'
        )

    def handle(self, *args, **options):
        # Создаем ресурс для экспорта
        resource = UserResource()
        
        # Создаем пустой queryset (только заголовки)
        queryset = User.objects.none()
        
        # Экспортируем в Excel
        xlsx_format = XLSX()
        export_data = resource.export(queryset)
        
        # Сохраняем в файл
        output_file = options['output']
        with open(output_file, 'wb') as f:
            f.write(export_data.xlsx)
        
        self.stdout.write(
            self.style.SUCCESS(f'Шаблон создан: {output_file}')
        )
        
        # Выводим инструкции
        self.stdout.write('\nИнструкции по заполнению:')
        self.stdout.write('1. Логин - уникальный логин пользователя')
        self.stdout.write('2. Фамилия, Имя, Отчество - обязательные поля')
        self.stdout.write('3. Телефон - в формате 8XXXXXXXXXX (11 цифр)')
        self.stdout.write('4. Email - необязательное поле')
        self.stdout.write('5. Роль - одна из: admin, brigadier, agitator, operator, analyst')
        self.stdout.write('6. Место работы - название из справочника мест работы')
        self.stdout.write('7. Активный участник - True/False (по умолчанию True)')
        self.stdout.write('8. Активен - True/False (по умолчанию True)')
        self.stdout.write('9. Дата создания - оставьте пустым')
        self.stdout.write('\nПримечание: ID оставьте пустым для новых записей')
