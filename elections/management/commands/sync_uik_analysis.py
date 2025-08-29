from django.core.management.base import BaseCommand
from elections.models import UIK, UIKAnalysis


class Command(BaseCommand):
    help = 'Синхронизирует все УИК с анализом - создает записи анализа для всех существующих УИК'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без выполнения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        all_uiks = UIK.objects.all()
        created_count = 0
        updated_count = 0
        
        self.stdout.write(f"Найдено УИК: {all_uiks.count()}")
        
        for uik in all_uiks:
            if dry_run:
                # Проверяем, существует ли уже запись анализа
                if UIKAnalysis.objects.filter(uik=uik).exists():
                    self.stdout.write(f"  УИК №{uik.number} - уже имеет запись анализа")
                    updated_count += 1
                else:
                    self.stdout.write(f"  УИК №{uik.number} - будет создана запись анализа")
                    created_count += 1
            else:
                # Создаем или обновляем запись анализа
                analysis, created = UIKAnalysis.objects.get_or_create(
                    uik=uik,
                    defaults={
                        'created_by': None,  # Системная команда
                        'updated_by': None,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"  ✅ Создана запись анализа для УИК №{uik.number}")
                else:
                    updated_count += 1
                    self.stdout.write(f"  ℹ️  УИК №{uik.number} уже имеет запись анализа")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР:"))
            self.stdout.write(f"  Будет создано: {created_count} записей")
            self.stdout.write(f"  Уже существует: {updated_count} записей")
            self.stdout.write(self.style.WARNING("Запустите без --dry-run для выполнения"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА:"))
            self.stdout.write(f"  Создано: {created_count} записей")
            self.stdout.write(f"  Обновлено: {updated_count} записей")
            self.stdout.write(f"  Всего УИК: {all_uiks.count()}")
