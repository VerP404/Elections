from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


class User(AbstractUser):
    """Расширенная модель пользователя с ролями"""
    
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('brigadier', 'Бригадир'),
        ('agitator', 'Агитатор'),
        ('operator', 'Оператор'),
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


class Workplace(models.Model):
    """Справочник мест работы"""
    
    name = models.CharField('Название организации', max_length=255, unique=True)
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
    ballot_box_votes = models.PositiveIntegerField('Урна', default=0)
    koib_votes = models.PositiveIntegerField('КОИБ', default=0)
    independent_votes = models.PositiveIntegerField('Самостоятельно', default=0)
    
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
        return self.ballot_box_votes + self.koib_votes + self.independent_votes
    
    @property
    def confirmed_voters_count(self):
        """Количество учтенных избирателей (проголосовавших) по данному УИК"""
        # Подсчитываем количество подтвержденных голосов через VotingRecord
        return VotingRecord.objects.filter(
            planned_voter__voter__uik=self.uik,
            confirmed_by_brigadier=True
        ).count()
    
    @property
    def ballot_box_percentage(self):
        if self.total_votes == 0:
            return Decimal('0.00')
        return round(Decimal(self.ballot_box_votes) / Decimal(self.total_votes) * 100, 2)
    
    @property
    def koib_percentage(self):
        if self.total_votes == 0:
            return Decimal('0.00')
        return round(Decimal(self.koib_votes) / Decimal(self.total_votes) * 100, 2)
    
    @property
    def independent_percentage(self):
        if self.total_votes == 0:
            return Decimal('0.00')
        return round(Decimal(self.independent_votes) / Decimal(self.total_votes) * 100, 2)


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
    voting_method = models.CharField(
        'Способ голосования',
        max_length=20,
        choices=[
            ('ballot_box', 'Урна'),
            ('koib', 'КОИБ'),
            ('independent', 'Самостоятельно'),
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



