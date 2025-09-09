from django.core.management.base import BaseCommand
from elections.models import UIKResultsDaily, VotingRecord
from datetime import date


class Command(BaseCommand):
    help = 'Пересчитывает все расчетные факты в UIKResultsDaily на основе подтвержденных голосований'

    def add_arguments(self, parser):
        parser.add_argument(
            '--uik',
            type=int,
            help='Пересчитать только для указанного УИК',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно пересчитать даже заблокированные значения',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет пересчитано без сохранения',
        )

    def handle(self, *args, **options):
        uik_number = options['uik']
        force = options['force']
        dry_run = options['dry_run']
        
        if uik_number:
            self.stdout.write(f'Пересчет для УИК {uik_number}...')
            queryset = UIKResultsDaily.objects.filter(uik__number=uik_number)
        else:
            self.stdout.write('Пересчет для всех УИК...')
            queryset = UIKResultsDaily.objects.all()

        if not queryset.exists():
            self.stdout.write(self.style.WARNING('Не найдено записей UIKResultsDaily для пересчета.'))
            return

        total_processed = 0
        total_updated = 0
        
        for instance in queryset:
            self.stdout.write(f'Обработка УИК {instance.uik.number}...')
            
            # Сохраняем старые значения для сравнения
            old_values = {
                'fact_12_sep_calculated': instance.fact_12_sep_calculated,
                'fact_13_sep_calculated': instance.fact_13_sep_calculated,
                'fact_14_sep_calculated': instance.fact_14_sep_calculated,
            }
            
            # Пересчитываем
            instance.calculate_daily_facts()
            
            # Проверяем изменения
            has_changes = (
                old_values['fact_12_sep_calculated'] != instance.fact_12_sep_calculated or
                old_values['fact_13_sep_calculated'] != instance.fact_13_sep_calculated or
                old_values['fact_14_sep_calculated'] != instance.fact_14_sep_calculated
            )
            
            if has_changes:
                self.stdout.write(f'  Изменения: 12.09: {old_values["fact_12_sep_calculated"]} → {instance.fact_12_sep_calculated}')
                self.stdout.write(f'             13.09: {old_values["fact_13_sep_calculated"]} → {instance.fact_13_sep_calculated}')
                self.stdout.write(f'             14.09: {old_values["fact_14_sep_calculated"]} → {instance.fact_14_sep_calculated}')
                
                if not dry_run:
                    # Обновляем эффективные факты
                    instance.update_effective_facts()
                    instance.save()
                    total_updated += 1
                else:
                    self.stdout.write('  [DRY RUN] Изменения не сохранены')
            else:
                self.stdout.write('  Изменений нет')
            
            total_processed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Обработано {total_processed} записей, изменений: {total_updated}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Пересчет завершен. Обработано {total_processed} записей, обновлено {total_updated}'))
