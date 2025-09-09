from django.core.management.base import BaseCommand
from elections.admin import UIKResource
from elections.models import UIK
from import_export.formats.base_formats import XLSX
import os

class Command(BaseCommand):
    help = 'Генерирует шаблон Excel для импорта УИК'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='uik_import_template.xlsx',
            help='Имя выходного файла'
        )

    def handle(self, *args, **options):
        resource = UIKResource()
        queryset = UIK.objects.none()  # Создаем пустой queryset для получения только заголовков
        
        export_data = resource.export(queryset)
        
        output_file = options['output']
        with open(output_file, 'wb') as f:
            f.write(export_data.xlsx)
        
        self.stdout.write(
            self.style.SUCCESS(f'Шаблон создан: {output_file}')
        )
        
        self.stdout.write('\nИнструкции по заполнению:')
        self.stdout.write('1. Номер УИК - уникальный номер участка')
        self.stdout.write('2. Адрес - полный адрес участка')
        self.stdout.write('3. Плановое количество избирателей - ожидаемое количество')
        self.stdout.write('4. Бригадир - ID или логин бригадира (должен существовать в системе)')
        self.stdout.write('5. Агитаторы - ID или логины агитаторов через запятую (должны существовать в системе)')
        self.stdout.write('\nПримеры:')
        self.stdout.write('- Бригадир: 1 или "brigadier1"')
        self.stdout.write('- Агитаторы: "1,2,3" или "agitator1,agitator2"')
        self.stdout.write('\nПримечание: ID оставьте пустым для новых записей')
