from django.core.management.base import BaseCommand
from elections.models import User, UIK


class Command(BaseCommand):
    help = 'Исправляет дублирующихся агитаторов - удаляет их из лишних УИК'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено без фактического изменения',
        )
        parser.add_argument(
            '--agitator-id',
            type=int,
            help='ID конкретного агитатора для исправления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        agitator_id = options.get('agitator_id')
        
        if agitator_id:
            # Исправляем конкретного агитатора
            try:
                agitator = User.objects.get(id=agitator_id, role='agitator')
                self.fix_agitator(agitator, dry_run)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Агитатор с ID {agitator_id} не найден')
                )
        else:
            # Ищем всех агитаторов с дублированием
            self.find_and_fix_duplicates(dry_run)

    def fix_agitator(self, agitator, dry_run):
        """Исправляет конкретного агитатора"""
        uiks = list(agitator.assigned_uiks_as_agitator.all())
        
        if len(uiks) <= 1:
            self.stdout.write(
                f'Агитатор {agitator.get_short_name()} назначен только на {len(uiks)} УИК'
            )
            return
        
        self.stdout.write(
            f'Агитатор {agitator.get_short_name()} назначен на {len(uiks)} УИК:'
        )
        
        for i, uik in enumerate(uiks):
            self.stdout.write(f'  {i+1}. УИК №{uik.number} - {uik.address[:50]}...')
        
        # Оставляем только первый УИК, остальные удаляем
        uiks_to_remove = uiks[1:]
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Будет удален из {len(uiks_to_remove)} УИК:'
                )
            )
            for uik in uiks_to_remove:
                self.stdout.write(f'  - УИК №{uik.number}')
        else:
            for uik in uiks_to_remove:
                uik.agitators.remove(agitator)
                self.stdout.write(
                    self.style.SUCCESS(f'Удален из УИК №{uik.number}')
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Агитатор {agitator.get_short_name()} теперь назначен только на УИК №{uiks[0].number}'
                )
            )

    def find_and_fix_duplicates(self, dry_run):
        """Ищет и исправляет всех дублирующихся агитаторов"""
        # Находим всех агитаторов
        agitators = User.objects.filter(role='agitator', is_active_participant=True)
        
        duplicates_found = 0
        fixed_count = 0
        
        for agitator in agitators:
            uik_count = agitator.assigned_uiks_as_agitator.count()
            
            if uik_count > 1:
                duplicates_found += 1
                self.stdout.write(
                    f'\nНайден дублирующийся агитатор: {agitator.get_short_name()} (ID: {agitator.id})'
                )
                self.stdout.write(f'Назначен на {uik_count} УИК')
                
                if not dry_run:
                    self.fix_agitator(agitator, dry_run)
                    fixed_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING('[DRY RUN] Будет исправлен при запуске без --dry-run')
                    )
        
        if duplicates_found == 0:
            self.stdout.write(
                self.style.SUCCESS('Дублирующихся агитаторов не найдено')
            )
        else:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n[DRY RUN] Найдено {duplicates_found} дублирующихся агитаторов'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nИсправлено {fixed_count} дублирующихся агитаторов'
                    )
                )
