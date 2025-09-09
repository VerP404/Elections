from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from datetime import date


class User(AbstractUser):
    """Расширенная модель пользователя с ролями"""
    
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('brigadier', 'Бригадир'),
        ('agitator', 'Агитатор'),
        ('operator', 'Оператор'),
        ('analyst', 'Аналитик'),
    ]
    
    # Кастомный валидатор для username с пробелами
    username_validator = RegexValidator(
        regex=r'^[\w\s@.+\-]+$',
        message='Имя пользователя может содержать только буквы, цифры, пробелы и символы @/./+/-/_.'
    )
    
    # Переопределяем username с кастомным валидатором
    username = models.CharField(
        'Логин',
        max_length=150,
        unique=True,
        validators=[username_validator],
        help_text='Обязательное поле. 150 символов или меньше. Может содержать буквы, цифры, пробелы и символы @/./+/-/_/.'
    )
    
    # Убираем email как обязательное поле
    email = models.EmailField('Email', blank=True, null=True)
    
    # Добавляем отчество как обязательное поле
    middle_name = models.CharField('Отчество', max_length=150)
    
    # Добавляем телефон как обязательное поле
    phone_regex = RegexValidator(
        regex=r'^8\d{10}$',
        message="Номер телефона должен быть в формате: '8XXXXXXXXXX'"
    )
    phone_number = models.CharField('Телефон', validators=[phone_regex], max_length=11, unique=True)
    
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='admin')
    workplace = models.ForeignKey(
        'Workplace', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='Место работы'
    )
    is_active_participant = models.BooleanField('Активный участник', default=True)
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверка уникальности пользователей в УИК
        if self.role in ['brigadier', 'agitator'] and self.pk is not None:
            # Проверяем, что пользователь не назначен в другие УИК
            if self.role == 'brigadier':
                other_uiks = UIK.objects.filter(brigadier=self).exclude(pk=getattr(self, 'pk', None))
                if other_uiks.exists():
                    raise ValidationError({
                        'role': 'Этот бригадир уже назначен в другой УИК.'
                    })
            elif self.role == 'agitator':
                other_uiks = UIK.objects.filter(agitators=self).exclude(pk=getattr(self, 'pk', None))
                if other_uiks.exists():
                    raise ValidationError({
                        'role': 'Этот агитатор уже назначен в другой УИК.'
                    })
    
    @property
    def is_agitator(self):
        return self.role == 'agitator'
    
    @property
    def is_brigadier(self):
        return self.role == 'brigadier'
    
    @property
    def is_operator(self):
        return self.role == 'operator'
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_analyst(self):
        return self.role == 'analyst'
    
    def get_full_name(self):
        """Полное имя пользователя"""
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
    def __str__(self):
        """Отображение пользователя с учетом роли"""
        return self.get_full_name()
    
    def get_full_name_with_role(self):
        """Полное имя с ролью"""
        full_name = self.get_full_name()
        role_name = dict(self.ROLE_CHOICES).get(self.role, self.role)
        return f"{full_name} ({role_name})"
    
    def get_display_name_for_voter(self):
        """Отображение для выбора в избирателе: ФИО агитатора"""
        return self.get_full_name()


class UIK(models.Model):
    """Модель участковых избирательных комиссий"""
    
    number = models.PositiveIntegerField('Номер УИК', unique=True)
    address = models.TextField('Адрес')
    planned_voters_count = models.PositiveIntegerField('Плановое количество избирателей', default=0, help_text='Ожидаемое количество избирателей на участке')
    
    # Связи с пользователями
    brigadier = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='Бригадир',
        limit_choices_to={'role': 'brigadier', 'is_active_participant': True},
        related_name='assigned_uik_as_brigadier'
    )
    agitators = models.ManyToManyField(
        User,
        verbose_name='Агитаторы',
        limit_choices_to={'role': 'agitator', 'is_active_participant': True},
        related_name='assigned_uiks_as_agitator',
        blank=True
    )
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_uiks')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_uiks')
    
    class Meta:
        verbose_name = 'УИК'
        verbose_name_plural = 'УИК'
        ordering = ['number']
        
    def __str__(self):
        return f"УИК №{self.number}"
    
    @property
    def actual_voters_count(self):
        """Фактическое количество избирателей"""
        return self.voter_set.count()
    
    @property
    def voters_difference(self):
        """Разница между плановым и фактическим количеством"""
        return self.actual_voters_count - self.planned_voters_count
    
    @property
    def agitators_display(self):
        """Отображение агитаторов для экспорта"""
        return ', '.join([agitator.get_full_name() for agitator in self.agitators.all()])
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что бригадир не назначен в другие УИК
        if self.brigadier:
            other_uiks = UIK.objects.filter(brigadier=self.brigadier).exclude(pk=self.pk)
            if other_uiks.exists():
                raise ValidationError({
                    'brigadier': 'Этот бригадир уже назначен в другой УИК.'
                })
        
        # Проверяем, что агитаторы не назначены в другие УИК
        # Проверяем только если экземпляр уже сохранен (имеет ID)
        if self.pk:
            for agitator in self.agitators.all():
                other_uiks = UIK.objects.filter(agitators=agitator).exclude(pk=self.pk)
                if other_uiks.exists():
                    raise ValidationError({
                        'agitators': f'Агитатор {agitator.get_full_name()} уже назначен в другой УИК.'
                    })
    
    def can_change_agitator(self, old_agitator, new_agitator):
        """Проверяет, можно ли сменить агитатора"""
        # Проверяем, что у старого агитатора есть планируемые избиратели
        planned_voters = PlannedVoter.objects.filter(agitator=old_agitator, voter__uik=self)
        return planned_voters.exists()
    
    def transfer_agitator_voters(self, old_agitator, new_agitator, user=None):
        """Переносит всех избирателей от старого агитатора к новому"""
        if not self.can_change_agitator(old_agitator, new_agitator):
            return False, "У агитатора нет планируемых избирателей"
        
        # Переносим всех планируемых избирателей
        planned_voters = PlannedVoter.objects.filter(agitator=old_agitator, voter__uik=self)
        transferred_count = 0
        
        for planned_voter in planned_voters:
            planned_voter.agitator = new_agitator
            if user:
                planned_voter.updated_by = user
            planned_voter.save()
            transferred_count += 1
        
        return True, f"Перенесено {transferred_count} избирателей"
    
    def remove_agitator_safely(self, agitator, user=None):
        """Безопасно удаляет агитатора, перенося его избирателей к другому агитатору"""
        # Находим другого агитатора в том же УИК
        other_agitators = self.agitators.exclude(id=agitator.id)
        
        if not other_agitators.exists():
            return False, "Нет других агитаторов для переноса избирателей"
        
        # Переносим к первому доступному агитатору
        new_agitator = other_agitators.first()
        success, message = self.transfer_agitator_voters(agitator, new_agitator, user)
        
        if success:
            # Удаляем агитатора из УИК
            self.agitators.remove(agitator)
            return True, f"{message}. Агитатор удален из УИК."
        
        return False, message


class Workplace(models.Model):
    """Справочник мест работы"""
    
    GROUP_CHOICES = [
        ('medicine', 'Медицина'),
        ('education', 'Образование'),
        ('social_protection', 'Соцзащита'),
        ('agitators', 'Агитаторы'),
        ('other', 'Прочие'),
    ]
    
    name = models.CharField('Название организации', max_length=255, unique=True)
    group = models.CharField(
        'Группа',
        max_length=20,
        choices=GROUP_CHOICES,
        default='other'
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_workplaces')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_workplaces')
    
    class Meta:
        verbose_name = 'Место работы'
        verbose_name_plural = 'Места работы'
        ordering = ['name']
        
    def __str__(self):
        return self.name


class Voter(models.Model):
    """Модель избирателей"""
    
    last_name = models.CharField('Фамилия', max_length=150)
    first_name = models.CharField('Имя', max_length=150)
    middle_name = models.CharField('Отчество', max_length=150, blank=True)
    birth_date = models.DateField('Дата рождения')
    registration_address = models.TextField('Адрес регистрации')
    
    phone_regex = RegexValidator(
        regex=r'^8\d{10}$',
        message="Номер телефона должен быть в формате: '8XXXXXXXXXX'"
    )
    phone_number = models.CharField('Телефон', validators=[phone_regex], max_length=11, blank=True)
    
    # Связи с другими моделями
    workplace = models.ForeignKey(Workplace, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Место работы')
    uik = models.ForeignKey(UIK, on_delete=models.CASCADE, verbose_name='УИК')
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_voters')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_voters')
    
    class Meta:
        verbose_name = 'Избиратель'
        verbose_name_plural = 'Избиратели'
        ordering = ['last_name', 'first_name']
        unique_together = ['last_name', 'first_name', 'middle_name', 'birth_date']
        
    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name} (УИК №{self.uik.number})".strip()
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
    @property
    def age(self):
        today = timezone.now().date()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))


class UIKResults(models.Model):
    """Результаты голосования по УИК"""
    
    uik = models.OneToOneField(UIK, on_delete=models.CASCADE, verbose_name='УИК', primary_key=True)
    
    # Результаты голосования
    at_uik_votes = models.PositiveIntegerField('В УИК', default=0)
    at_home_votes = models.PositiveIntegerField('На дому', default=0)
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Результат по УИК'
        verbose_name_plural = 'Результаты по УИК'
        ordering = ['uik__number']
        
    def __str__(self):
        return f"Результаты УИК №{self.uik.number}"
    
    @property
    def total_votes(self):
        return self.at_uik_votes + self.at_home_votes
    
    @property
    def confirmed_voters_count(self):
        """Количество учтенных избирателей (проголосовавших) по данному УИК"""
        # Подсчитываем количество подтвержденных голосов через VotingRecord
        return VotingRecord.objects.filter(
            planned_voter__voter__uik=self.uik,
            confirmed_by_brigadier=True
        ).count()
    
    @property
    def at_uik_percentage(self):
        if self.total_votes == 0:
            return Decimal('0.00')
        return round(Decimal(self.at_uik_votes) / Decimal(self.total_votes) * 100, 2)
    
    @property
    def at_home_percentage(self):
        if self.total_votes == 0:
            return Decimal('0.00')
        return round(Decimal(self.at_home_votes) / Decimal(self.total_votes) * 100, 2)


class PlannedVoter(models.Model):
    """Планирование избирателей агитаторами"""
    
    STATUS_CHOICES = [
        ('planned', 'Запланирован'),
        ('refused', 'Отказался'),
        ('voted', 'Проголосовал'),
    ]
    
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE, verbose_name='Избиратель')
    agitator = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name='Агитатор',
        limit_choices_to={'role': 'agitator', 'is_active_participant': True}
    )
    planned_date = models.DateField('Планируемая дата голосования', null=True, blank=True)
    notes = models.TextField('Заметки', blank=True)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned'
    )
    

    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что агитатор прикреплен к УИК избирателя
        if self.voter and self.agitator:
            if not self.voter.uik.agitators.filter(id=self.agitator.id).exists():
                raise ValidationError({
                    'agitator': 'Этот агитатор не прикреплен к УИК данного избирателя.'
                })
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_planned_voters')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_planned_voters')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Планируемый избиратель'
        verbose_name_plural = 'Планируемые избиратели'
        unique_together = ['voter', 'agitator']
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.voter} - {self.agitator}"
    
    @property
    def has_voting_record(self):
        """Есть ли запись о голосовании"""
        return hasattr(self, 'votingrecord')
    
    def save(self, *args, **kwargs):
        """Автоматически создаем запись о голосовании при создании планируемого избирателя"""
        is_new = self.pk is None
        old_status = None
        if not is_new:
            try:
                old_instance = PlannedVoter.objects.get(pk=self.pk)
                old_status = old_instance.status
            except PlannedVoter.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Создаем запись о голосовании для новых записей со статусом "Запланирован"
        if is_new and self.status == 'planned' and not hasattr(self, 'votingrecord'):
            VotingRecord.objects.create(
                planned_voter=self,
                created_by=self.created_by,
                updated_by=self.updated_by
            )
        
        # Если статус изменился на "отказался", удаляем запись о голосовании
        if not is_new and old_status != 'refused' and self.status == 'refused':
            if hasattr(self, 'votingrecord'):
                self.votingrecord.delete()
        
        # Если статус изменился на "проголосовал", создаем запись о голосовании если её нет
        if not is_new and old_status != 'voted' and self.status == 'voted':
            if not hasattr(self, 'votingrecord'):
                VotingRecord.objects.create(
                    planned_voter=self,
                    created_by=self.created_by,
                    updated_by=self.updated_by
                )
        
        # Если статус изменился на "запланирован", создаем запись о голосовании если её нет
        if not is_new and old_status != 'planned' and self.status == 'planned':
            if not hasattr(self, 'votingrecord'):
                VotingRecord.objects.create(
                    planned_voter=self,
                    created_by=self.created_by,
                    updated_by=self.updated_by
                )
    
    def update_status_from_voting_record(self):
        """Автоматически обновляем статус на основе записи о голосовании"""
        if hasattr(self, 'votingrecord') and self.votingrecord:
            if self.votingrecord.confirmed_by_brigadier:
                if self.status != 'voted':
                    self.status = 'voted'
                    self.save(update_fields=['status'])
            elif self.votingrecord.voting_date and not self.votingrecord.confirmed_by_brigadier:
                if self.status != 'planned':
                    self.status = 'planned'
                    self.save(update_fields=['status'])
        else:
            if self.status != 'planned':
                self.status = 'planned'
                self.save(update_fields=['status'])
    



class VotingRecord(models.Model):
    """Запись о голосовании избирателя"""
    
    planned_voter = models.OneToOneField(
        PlannedVoter, 
        on_delete=models.CASCADE, 
        verbose_name='Планируемый избиратель'
    )
    voting_date = models.DateField('Дата голосования', null=True, blank=True)
    
    def clean(self):
        """Валидация даты голосования - только 12, 13, 14 сентября"""
        if self.voting_date:
            # Проверяем, что дата входит в разрешенный период
            allowed_dates = [
                date(2025, 9, 12),  # 12 сентября 2025
                date(2025, 9, 13),  # 13 сентября 2025
                date(2025, 9, 14),  # 14 сентября 2025
            ]
            if self.voting_date not in allowed_dates:
                raise ValidationError({
                    'voting_date': 'Дата голосования должна быть 12, 13 или 14 сентября 2025 года'
                })
    
    def save(self, *args, **kwargs):
        """Переопределяем save для валидации"""
        self.clean()
        super().save(*args, **kwargs)
    voting_method = models.CharField(
        'Способ голосования',
        max_length=20,
        choices=[
            ('at_uik', 'В УИК'),
            ('at_home', 'На дому'),
        ],
        blank=True
    )
    confirmed_by_brigadier = models.BooleanField('Подтверждено бригадиром', default=False)
    brigadier_notes = models.TextField('Заметки бригадира', blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_voting_records')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_voting_records')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Запись о голосовании'
        verbose_name_plural = 'Записи о голосовании'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Голосование {self.planned_voter.voter} - {self.voting_date}"
    
    @property
    def is_confirmed(self):
        """Подтверждено ли голосование"""
        return self.confirmed_by_brigadier and self.voting_date is not None


class UIKAnalysis(models.Model):
    """Анализ по УИК - планы и факты по дому и участку"""
    
    uik = models.OneToOneField(UIK, on_delete=models.CASCADE, verbose_name='УИК', primary_key=True)
    
    # Планы
    home_plan = models.PositiveIntegerField('План на дому', default=0, help_text='Планируемое количество голосов на дому')
    site_plan = models.PositiveIntegerField('План на участке', default=0, help_text='Планируемое количество голосов на участке')
    
    # Факты
    home_fact = models.PositiveIntegerField('Факт на дому', default=0, help_text='Фактическое количество голосов на дому')
    site_fact = models.PositiveIntegerField('Факт на участке', default=0, help_text='Фактическое количество голосов на участке')
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_uik_analyses')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_uik_analyses')
    
    class Meta:
        verbose_name = 'Анализ по УИК'
        verbose_name_plural = 'Анализ по УИК'
        ordering = ['uik__number']
        
    def __str__(self):
        return f"Анализ УИК №{self.uik.number}"
    
    @property
    def total_plan(self):
        """Общий план (автоматически рассчитывается)"""
        return self.home_plan + self.site_plan
    
    @property
    def total_fact(self):
        """Общий факт (автоматически рассчитывается)"""
        return self.home_fact + self.site_fact
    
    @property
    def plan_execution_percentage(self):
        """Процент выполнения плана"""
        if self.total_plan == 0:
            return Decimal('0.00')
        return round(Decimal(self.total_fact) / Decimal(self.total_plan) * 100, 2)
    
    @property
    def home_execution_percentage(self):
        """Процент выполнения плана на дому"""
        if self.home_plan == 0:
            return Decimal('0.00')
        return round(Decimal(self.home_fact) / Decimal(self.home_plan) * 100, 2)
    
    @property
    def site_execution_percentage(self):
        """Процент выполнения плана на участке"""
        if self.site_plan == 0:
            return Decimal('0.00')
        return round(Decimal(self.site_fact) / Decimal(self.site_plan) * 100, 2)


class UIKResultsDaily(models.Model):
    """Результаты голосования по УИК по дням"""
    
    uik = models.OneToOneField(UIK, on_delete=models.CASCADE, verbose_name='УИК', primary_key=True)
    
    # План по дням голосования
    plan_12_sep = models.PositiveIntegerField('План 12.09', default=0, help_text='Плановое количество голосов 12 сентября')
    plan_13_sep = models.PositiveIntegerField('План 13.09', default=0, help_text='Плановое количество голосов 13 сентября')
    plan_14_sep = models.PositiveIntegerField('План 14.09', default=0, help_text='Плановое количество голосов 14 сентября')
    
    # Факты по дням голосования (ручные)
    fact_12_sep = models.PositiveIntegerField('Факт 12.09', default=0, help_text='Фактическое количество голосов 12 сентября')
    fact_13_sep = models.PositiveIntegerField('Факт 13.09', default=0, help_text='Фактическое количество голосов 13 сентября')
    fact_14_sep = models.PositiveIntegerField('Факт 14.09', default=0, help_text='Фактическое количество голосов 14 сентября')
    
    # Расчетные факты по дням голосования
    fact_12_sep_calculated = models.PositiveIntegerField('Расчет', default=0, help_text='Автоматически рассчитываемое количество голосов 12 сентября')
    fact_13_sep_calculated = models.PositiveIntegerField('Расчет', default=0, help_text='Автоматически рассчитываемое количество голосов 13 сентября')
    fact_14_sep_calculated = models.PositiveIntegerField('Расчет', default=0, help_text='Автоматически рассчитываемое количество голосов 14 сентября')
    
    # Флаги блокировки для каждого дня
    fact_12_sep_locked = models.BooleanField('Блок 12.09', default=False, help_text='Заблокировать значение - использовать только ручное')
    fact_13_sep_locked = models.BooleanField('Блок 13.09', default=False, help_text='Заблокировать значение - использовать только ручное')
    fact_14_sep_locked = models.BooleanField('Блок 14.09', default=False, help_text='Заблокировать значение - использовать только ручное')
    
    # Источник текущего значения для каждого дня
    fact_12_sep_source = models.CharField('Источник 12.09', max_length=20, choices=[('manual', 'Ручное'), ('calculated', 'Расчетное')], default='manual')
    fact_13_sep_source = models.CharField('Источник 13.09', max_length=20, choices=[('manual', 'Ручное'), ('calculated', 'Расчетное')], default='manual')
    fact_14_sep_source = models.CharField('Источник 14.09', max_length=20, choices=[('manual', 'Ручное'), ('calculated', 'Расчетное')], default='manual')
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создал', related_name='created_uik_results_daily')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Изменил', related_name='updated_uik_results_daily')
    
    class Meta:
        verbose_name = 'Результаты по дням УИК'
        verbose_name_plural = 'Результаты по дням УИК'
        ordering = ['uik__number']
        
    def __str__(self):
        return f"Результаты по дням УИК №{self.uik.number}"
    
    @property
    def total_plan(self):
        """Общий план по всем дням (автоматически рассчитывается)"""
        return self.plan_12_sep + self.plan_13_sep + self.plan_14_sep
    
    @property
    def total_fact(self):
        """Общий факт по всем дням (автоматически рассчитывается)"""
        return self.fact_12_sep + self.fact_13_sep + self.fact_14_sep
    
    @property
    def plan_execution_percentage(self):
        """Процент выполнения плана по дням"""
        if self.total_plan == 0:
            return Decimal('0.00')
        return round(Decimal(self.total_fact) / Decimal(self.total_plan) * 100, 2)
    
    def get_effective_fact_12_sep(self):
        """Получить эффективное значение факта за 12.09 с учетом блокировки"""
        if self.fact_12_sep_locked:
            return self.fact_12_sep
        else:
            # Если не заблокировано - используем максимальное из ручного и расчетного
            return max(self.fact_12_sep, self.fact_12_sep_calculated)
    
    def get_effective_fact_13_sep(self):
        """Получить эффективное значение факта за 13.09 с учетом блокировки"""
        if self.fact_13_sep_locked:
            return self.fact_13_sep
        else:
            # Если не заблокировано - используем максимальное из ручного и расчетного
            return max(self.fact_13_sep, self.fact_13_sep_calculated)
    
    def get_effective_fact_14_sep(self):
        """Получить эффективное значение факта за 14.09 с учетом блокировки"""
        if self.fact_14_sep_locked:
            return self.fact_14_sep
        else:
            # Если не заблокировано - используем максимальное из ручного и расчетного
            return max(self.fact_14_sep, self.fact_14_sep_calculated)
    
    def update_effective_facts(self):
        """Обновить эффективные значения фактов на основе логики переключения"""
        # Обновляем источник для каждого дня
        if not self.fact_12_sep_locked:
            if self.fact_12_sep_calculated >= self.fact_12_sep:
                self.fact_12_sep_source = 'calculated'
            else:
                self.fact_12_sep_source = 'manual'
        
        if not self.fact_13_sep_locked:
            if self.fact_13_sep_calculated >= self.fact_13_sep:
                self.fact_13_sep_source = 'calculated'
            else:
                self.fact_13_sep_source = 'manual'
        
        if not self.fact_14_sep_locked:
            if self.fact_14_sep_calculated >= self.fact_14_sep:
                self.fact_14_sep_source = 'calculated'
            else:
                self.fact_14_sep_source = 'manual'
    
    def calculate_daily_facts(self):
        """Рассчитать факты по дням на основе подтвержденных голосований"""
        from datetime import date
        
        # Получаем все подтвержденные голосования для этого УИК
        confirmed_votings = VotingRecord.objects.filter(
            planned_voter__voter__uik=self.uik,
            confirmed_by_brigadier=True,
            voting_date__isnull=False
        )
        
        # Считаем голосования по дням
        fact_12_count = confirmed_votings.filter(voting_date=date(2025, 9, 12)).count()
        fact_13_count = confirmed_votings.filter(voting_date=date(2025, 9, 13)).count()
        fact_14_count = confirmed_votings.filter(voting_date=date(2025, 9, 14)).count()
        
        # Обновляем расчетные значения
        self.fact_12_sep_calculated = fact_12_count
        self.fact_13_sep_calculated = fact_13_count
        self.fact_14_sep_calculated = fact_14_count
        pass
    
    def recalculate_all(self):
        """Пересчитать все расчетные значения и обновить эффективные факты"""
        self.calculate_daily_facts()
        self.update_effective_facts()
        
        # Перезаписываем fact_XX_sep на эффективные значения если не заблокировано
        if not self.fact_12_sep_locked:
            self.fact_12_sep = max(self.fact_12_sep, self.fact_12_sep_calculated)
        if not self.fact_13_sep_locked:
            self.fact_13_sep = max(self.fact_13_sep, self.fact_13_sep_calculated)
        if not self.fact_14_sep_locked:
            self.fact_14_sep = max(self.fact_14_sep, self.fact_14_sep_calculated)
        
        self.save(update_fields=[
            'fact_12_sep_calculated', 'fact_13_sep_calculated', 'fact_14_sep_calculated',
            'fact_12_sep', 'fact_13_sep', 'fact_14_sep',
            'fact_12_sep_source', 'fact_13_sep_source', 'fact_14_sep_source'
        ])
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического обновления логики"""
        # Обновляем эффективные факты перед сохранением
        self.update_effective_facts()
        super().save(*args, **kwargs)


class Analytics(models.Model):
    """Модель для аналитических данных"""
    
    title = models.CharField('Заголовок', max_length=255)
    description = models.TextField('Описание', blank=True)
    data = models.JSONField('Данные', default=dict)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Создал')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Аналитика'
        verbose_name_plural = 'Аналитика'
        ordering = ['-created_at']
        
    def __str__(self):
        return self.title


# Сигналы для автоматического обновления данных
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=VotingRecord)
def update_planned_voter_status(sender, instance, created, **kwargs):
    """Автоматически обновляем статус планируемого избирателя при изменении записи о голосовании"""
    if instance.planned_voter:
        instance.planned_voter.update_status_from_voting_record()
        
        # Пересчитываем UIKResultsDaily при любом изменении подтверждения или даты голосования
        if instance.voting_date:
            try:
                uik_results_daily = UIKResultsDaily.objects.get(uik=instance.planned_voter.voter.uik)
                uik_results_daily.recalculate_all()
            except UIKResultsDaily.DoesNotExist:
                # Создаем запись если её нет
                UIKResultsDaily.objects.create(uik=instance.planned_voter.voter.uik)
                uik_results_daily = UIKResultsDaily.objects.get(uik=instance.planned_voter.voter.uik)
                uik_results_daily.recalculate_all()


@receiver(post_save, sender=UIK)
def create_uik_analysis(sender, instance, created, **kwargs):
    """Автоматически создаем запись анализа при создании УИК"""
    if created:
        UIKAnalysis.objects.create(uik=instance)
        UIKResultsDaily.objects.create(uik=instance)



