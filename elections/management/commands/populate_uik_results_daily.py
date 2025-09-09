from django.core.management.base import BaseCommand
from elections.models import UIK, UIKResultsDaily


class Command(BaseCommand):
    help = 'Заполняет таблицу UIKResultsDaily данными из существующих УИК'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет создано без фактического создания записей',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Получаем все УИК
        uiks = UIK.objects.all()
        
        if not uiks.exists():
            self.stdout.write(
                self.style.WARNING('Нет УИК в базе данных')
            )
            return
        
        created_count = 0
        existing_count = 0
        
        for uik in uiks:
            # Проверяем, существует ли уже запись для этого УИК
            if UIKResultsDaily.objects.filter(uik=uik).exists():
                existing_count += 1
                self.stdout.write(
                    f'УИК №{uik.number} уже имеет запись в UIKResultsDaily'
                )
                continue
            
            if not dry_run:
                # Создаем запись для УИК
                UIKResultsDaily.objects.create(uik=uik)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Создана запись для УИК №{uik.number}')
                )
            else:
                created_count += 1
                self.stdout.write(
                    f'[DRY RUN] Будет создана запись для УИК №{uik.number}'
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Результат:\n'
                    f'- Будет создано записей: {created_count}\n'
                    f'- Уже существует записей: {existing_count}\n'
                    f'- Всего УИК: {uiks.count()}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nРезультат:\n'
                    f'- Создано записей: {created_count}\n'
                    f'- Уже существовало записей: {existing_count}\n'
                    f'- Всего УИК: {uiks.count()}'
                )
            )
