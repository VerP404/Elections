from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal


class User(AbstractUser):
    """Расширенная модель пользователя с дополнительными полями"""
    
    last_name = models.CharField('Фамилия', max_length=150)
    first_name = models.CharField('Имя', max_length=150)
    middle_name = models.CharField('Отчество', max_length=150, blank=True)
    email = models.EmailField('Email', unique=True)
    
    phone_regex = RegexValidator(
        regex=r'^8\d{10}$',
        message="Номер телефона должен быть в формате: '8XXXXXXXXXX'"
    )
    phone_number = models.CharField('Телефон', validators=[phone_regex], max_length=11, unique=True)
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name', 'phone_number']
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        
    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()


class UIK(models.Model):
    """Модель участковых избирательных комиссий"""
    
    number = models.PositiveIntegerField('Номер УИК', unique=True)
    address = models.TextField('Адрес')
    planned_voters_count = models.PositiveIntegerField('Плановое количество избирателей', default=0, help_text='Ожидаемое количество избирателей на участке')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
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


class Workplace(models.Model):
    """Справочник мест работы"""
    
    name = models.CharField('Название организации', max_length=255, unique=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Место работы'
        verbose_name_plural = 'Места работы'
        ordering = ['name']
        
    def __str__(self):
        return self.name


class Participant(models.Model):
    """Участники избирательного процесса (агитаторы и бригадиры)"""
    
    ROLE_CHOICES = [
        ('agitator', 'Агитатор'),
        ('brigadier', 'Бригадир'),
        ('both', 'Агитатор и бригадир'),
    ]
    
    last_name = models.CharField('Фамилия', max_length=150)
    first_name = models.CharField('Имя', max_length=150)
    middle_name = models.CharField('Отчество', max_length=150, blank=True)
    phone_regex = RegexValidator(
        regex=r'^8\d{10}$',
        message="Номер телефона должен быть в формате: '8XXXXXXXXXX'"
    )
    phone_number = models.CharField('Телефон', validators=[phone_regex], max_length=11, blank=True)
    
    role = models.CharField('Роль', max_length=10, choices=ROLE_CHOICES, default='agitator')
    is_active = models.BooleanField('Активен', default=True)
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Участник'
        verbose_name_plural = 'Участники'
        ordering = ['last_name', 'first_name']
        
    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
    @property
    def is_agitator(self):
        return self.role in ['agitator', 'both']
    
    @property
    def is_brigadier(self):
        return self.role in ['brigadier', 'both']


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
    agitator = models.ForeignKey(
        Participant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='agitated_voters',
        verbose_name='Агитатор',
        limit_choices_to={'role__in': ['agitator', 'both']}
    )
    brigadier = models.ForeignKey(
        Participant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='supervised_voters',
        verbose_name='Бригадир',
        limit_choices_to={'role__in': ['brigadier', 'both']}
    )
    
    # Блок голосования
    voting_date = models.DateField('Дата голосования', null=True, blank=True)
    voting_confirmed = models.BooleanField('Подтверждение голосования', default=False)
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Избиратель'
        verbose_name_plural = 'Избиратели'
        ordering = ['last_name', 'first_name']
        unique_together = ['last_name', 'first_name', 'middle_name', 'birth_date']
        
    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
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
        return self.uik.voter_set.filter(voting_confirmed=True).count()
    
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
