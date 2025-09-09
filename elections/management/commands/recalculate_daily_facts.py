from django.core.management.base import BaseCommand
from elections.models import UIKResultsDaily


class Command(BaseCommand):
    help = 'Пересчитать расчетные факты для всех УИК'

    def add_arguments(self, parser):
        parser.add_argument(
            '--uik',
            type=int,
            help='Номер УИК для пересчета (если не указан, пересчитываются все)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно пересчитать даже заблокированные значения',
        )

    def handle(self, *args, **options):
        uik_number = options.get('uik')
        force = options.get('force', False)
        
        if uik_number:
            try:
                daily_result = UIKResultsDaily.objects.get(uik__number=uik_number)
                self.recalculate_single(daily_result, force)
                self.stdout.write(
                    self.style.SUCCESS(f'Успешно пересчитан УИК №{uik_number}')
                )
            except UIKResultsDaily.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'УИК №{uik_number} не найден')
                )
        else:
            # Пересчитываем все УИК
            daily_results = UIKResultsDaily.objects.all()
            count = 0
            
            for daily_result in daily_results:
                if self.recalculate_single(daily_result, force):
                    count += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'Успешно пересчитано {count} УИК')
            )

    def recalculate_single(self, daily_result, force=False):
        """Пересчитать один УИК"""
        if not force and (daily_result.fact_12_sep_locked or 
                         daily_result.fact_13_sep_locked or 
                         daily_result.fact_14_sep_locked):
            self.stdout.write(
                self.style.WARNING(
                    f'УИК №{daily_result.uik.number} заблокирован, пропускаем'
                )
            )
            return False
        
        try:
            daily_result.recalculate_all()
            return True
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Ошибка при пересчете УИК №{daily_result.uik.number}: {e}'
                )
            )
            return False
