from django.core.management.base import BaseCommand
from elections.admin import WorkplaceResource
from elections.models import Workplace


class Command(BaseCommand):
    help = 'Генерирует шаблон Excel для импорта мест работы'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='workplace_import_template.xlsx',
            help='Имя выходного файла'
        )

    def handle(self, *args, **options):
        # Создаем ресурс для экспорта
        resource = WorkplaceResource()
        
        # Создаем пустой queryset (только заголовки)
        queryset = Workplace.objects.none()
        
        # Экспортируем в Excel (с инструкциями)
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
        self.stdout.write('1. Название организации - уникальное название')
        self.stdout.write('2. Группа - одна из: medicine, education, social_protection, agitators, other')
        self.stdout.write('3. Дата создания - оставьте пустым')
        self.stdout.write('\nПримечание: ID оставьте пустым для новых записей')
        self.stdout.write('\nПримеры групп:')
        self.stdout.write('- medicine = Медицина')
        self.stdout.write('- education = Образование')
        self.stdout.write('- social_protection = Соцзащита')
        self.stdout.write('- agitators = Агитаторы')
        self.stdout.write('- other = Прочие')
