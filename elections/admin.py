from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from import_export.formats.base_formats import XLSX, CSV, XLS
from django.db import models
from django.contrib.auth import get_user_model

from .models import User, UIK, Workplace, Participant, Voter, UIKResults, Analytics


# Перерегистрируем стандартную модель Group с нашим стилем
admin.site.unregister(Group)

@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    """Админка для групп пользователей"""
    
    list_display = ['name', 'users_count', 'permissions_count']
    search_fields = ['name']
    filter_horizontal = ('permissions',)
    
    @display(description='Пользователей')
    def users_count(self, obj):
        return obj.user_set.count()
    
    @display(description='Разрешений')
    def permissions_count(self, obj):
        return obj.permissions.count()


# Ресурсы для импорта-экспорта
class WorkplaceResource(resources.ModelResource):
    """Ресурс для импорта-экспорта мест работы"""
    
    class Meta:
        model = Workplace
        fields = ('id', 'name', 'created_at')
        export_order = ('id', 'name', 'created_at')
        import_id_fields = ('name',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    # Удалена проверка на дублирование — теперь записи будут обновляться по name
    
    def get_export_headers(self, selected_fields=None):
        """Русские заголовки для экспорта"""
        # selected_fields нужен для совместимости с import-export >= 3.0
        if selected_fields is not None:
            # Используем стандартную обработку, если выбранные поля заданы
            return super().get_export_headers(selected_fields=selected_fields)
        return ['ID', 'Название организации', 'Дата создания']


class UIKResource(resources.ModelResource):
    """Ресурс для импорта-экспорта УИК"""
    
    class Meta:
        model = UIK
        fields = ('id', 'number', 'address', 'planned_voters_count', 'created_at')
        export_order = ('id', 'number', 'address', 'planned_voters_count', 'created_at')
        import_id_fields = ('number',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    # Удалена проверка на дублирование — теперь записи будут обновляться по number
    
    def get_export_headers(self, selected_fields=None):
        """Русские заголовки для экспорта"""
        if selected_fields is not None:
            return super().get_export_headers(selected_fields=selected_fields)
        return ['ID', 'Номер УИК', 'Адрес', 'Плановое количество избирателей', 'Дата создания']


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Админка для пользователей"""
    
    list_display = ['email', 'get_full_name', 'phone_number', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active', 'date_joined', 'groups']
    search_fields = ['email', 'first_name', 'last_name', 'middle_name', 'phone_number']
    ordering = ['email']
    filter_horizontal = ('groups', 'user_permissions')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Персональная информация', {
            'fields': ('first_name', 'last_name', 'middle_name', 'phone_number')
        }),
        ('Разрешения', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'middle_name', 'phone_number', 'password1', 'password2'),
        }),
    )
    
    @display(description='ФИО')
    def get_full_name(self, obj):
        return obj.get_full_name()


@admin.register(UIK)
class UIKAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для УИК с импортом-экспортом"""
    
    resource_class = UIKResource
    list_display = ['number', 'address_short', 'planned_voters_count', 'actual_voters_count', 'voters_difference', 'has_results']
    list_filter = ['created_at']
    search_fields = ['number', 'address']
    ordering = ['number']
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    def has_view_permission(self, request, obj=None):
        """Ограничение просмотра списка для обычных пользователей"""
        # Суперпользователи и staff видят все
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Для обычных пользователей
        if obj is None:  # Список объектов
            return False  # Запрещаем просмотр списка
        else:  # Конкретный объект
            return True  # Разрешаем просмотр конкретного объекта
    
    def has_add_permission(self, request):
        """Разрешение на добавление"""
        return request.user.has_perm('elections.add_uik')
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_uik')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_uik')
    
    @display(description='Адрес')
    def address_short(self, obj):
        return obj.address[:50] + '...' if len(obj.address) > 50 else obj.address
    
    @display(description='Плановое кол-во')
    def planned_voters_count(self, obj):
        return obj.planned_voters_count
    
    @display(description='Фактическое кол-во')
    def actual_voters_count(self, obj):
        return obj.actual_voters_count
    
    @display(description='Разница')
    def voters_difference(self, obj):
        diff = obj.voters_difference
        if diff > 0:
            return format_html('<span style="color: green;">+{}</span>', diff)
        elif diff < 0:
            return format_html('<span style="color: red;">{}</span>', diff)
        else:
            return format_html('<span style="color: gray;">0</span>')
    
    @display(description='Есть результаты', boolean=True)
    def has_results(self, obj):
        return hasattr(obj, 'uikresults')


@admin.register(Workplace)
class WorkplaceAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для мест работы с импортом-экспортом"""
    
    resource_class = WorkplaceResource
    list_display = ['name', 'workers_count', 'created_at']
    search_fields = ['name']
    ordering = ['name']
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    def has_view_permission(self, request, obj=None):
        """Ограничение просмотра списка для обычных пользователей"""
        # Суперпользователи и staff видят все
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Для обычных пользователей
        if obj is None:  # Список объектов
            return False  # Запрещаем просмотр списка
        else:  # Конкретный объект
            return True  # Разрешаем просмотр конкретного объекта
    
    def has_add_permission(self, request):
        """Разрешение на добавление"""
        return request.user.has_perm('elections.add_workplace')
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_workplace')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_workplace')
    
    def save_model(self, request, obj, form, change):
        """Проверка на уникальность при сохранении"""
        if not change:  # Новая запись
            if Workplace.objects.filter(name__iexact=obj.name).exists():
                from django.core.exceptions import ValidationError
                raise ValidationError(f'Место работы "{obj.name}" уже существует')
        super().save_model(request, obj, form, change)
    
    @display(description='Сотрудников')
    def workers_count(self, obj):
        return obj.voter_set.count()

    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        if is_operators_user(request.user):
            # Только просмотр, добавление и изменение
            return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}
        return perms


@admin.register(Participant)
class ParticipantAdmin(ModelAdmin):
    """Админка для участников"""
    
    list_display = ['get_full_name', 'role', 'phone_number', 'agitated_count', 'supervised_count', 'is_active']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['first_name', 'last_name', 'middle_name', 'phone_number']
    ordering = ['last_name', 'first_name']
    
    def has_view_permission(self, request, obj=None):
        """Ограничение просмотра списка для обычных пользователей"""
        # Суперпользователи и staff видят все
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Для обычных пользователей
        if obj is None:  # Список объектов
            return False  # Запрещаем просмотр списка
        else:  # Конкретный объект
            return True  # Разрешаем просмотр конкретного объекта
    
    def has_add_permission(self, request):
        """Разрешение на добавление"""
        return request.user.has_perm('elections.add_participant')
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_participant')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_participant')
    
    @display(description='ФИО')
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    @display(description='Агитирует')
    def agitated_count(self, obj):
        return obj.agitated_voters.count() if obj.is_agitator else '-'
    
    @display(description='Контролирует')
    def supervised_count(self, obj):
        return obj.supervised_voters.count() if obj.is_brigadier else '-'


class VoterInline(TabularInline):
    """Инлайн для избирателей в УИК"""
    model = Voter
    extra = 0
    fields = ['last_name', 'first_name', 'middle_name', 'birth_date', 'voting_confirmed']
    readonly_fields = ['last_name', 'first_name', 'middle_name', 'birth_date']


@admin.register(Voter)
class VoterAdmin(ModelAdmin):
    """Админка для избирателей"""
    
    list_display = [
        'get_full_name', 'age', 'uik', 'phone_number', 
        'agitator', 'brigadier', 'voting_status', 'workplace'
    ]
    list_filter = [
        'uik', 'agitator', 'brigadier', 'workplace',
        'voting_confirmed', 'voting_date', 'birth_date'
    ]
    search_fields = [
        'first_name', 'last_name', 'middle_name', 
        'phone_number', 'registration_address'
    ]
    ordering = ['last_name', 'first_name']
    
    fieldsets = (
        ('Персональные данные', {
            'fields': ('first_name', 'last_name', 'middle_name', 'birth_date', 'phone_number')
        }),
        ('Адрес и место работы', {
            'fields': ('registration_address', 'workplace')
        }),
        ('Избирательная комиссия', {
            'fields': ('uik',)
        }),
        ('Работа с избирателем', {
            'fields': ('agitator', 'brigadier')
        }),
        ('Голосование', {
            'fields': ('voting_date', 'voting_confirmed'),
            'classes': ('collapse',)
        }),
    )
    
    def has_view_permission(self, request, obj=None):
        """Разрешения на просмотр"""
        return request.user.has_perm('elections.view_voter')
    
    def has_add_permission(self, request):
        """Разрешение на добавление"""
        return request.user.has_perm('elections.add_voter')
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_voter')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_voter')
    
    @display(description='ФИО')
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    @display(description='Возраст')
    def age(self, obj):
        return f"{obj.age} лет"
    
    @display(description='Статус голосования')
    def voting_status(self, obj):
        if obj.voting_confirmed:
            return format_html(
                '<span style="color: green;">✓ Проголосовал</span>'
            )
        elif obj.voting_date:
            return format_html(
                '<span style="color: orange;">📅 {}</span>', 
                obj.voting_date.strftime('%d.%m.%Y')
            )
        else:
            return format_html(
                '<span style="color: red;">❌ Не определен</span>'
            )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_operators_user(request.user) and not request.user.is_superuser:
            # Показываем только записи, где оператор - агитатор или бригадир
            return qs.filter(
                models.Q(agitator__phone_number=request.user.phone_number) |
                models.Q(brigadier__phone_number=request.user.phone_number)
            ).distinct()
        return qs

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if is_operators_user(request.user):
            if obj is None:
                return True
            # Оператор может менять только свои записи
            return (
                (obj.agitator and obj.agitator.phone_number == request.user.phone_number) or
                (obj.brigadier and obj.brigadier.phone_number == request.user.phone_number)
            )
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Операторы не могут удалять
        if is_operators_user(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        if is_operators_user(request.user):
            # Только просмотр, добавление и изменение
            return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}
        return perms


@admin.register(UIKResults)
class UIKResultsAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для результатов по УИК с редактированием в списке"""
    
    list_display = [
        'uik', 'planned_voters_count', 'confirmed_voters_count', 'confirmed_percent',
        'ballot_box_votes', 'koib_votes', 'independent_votes',
        'total_votes', 'ballot_box_percentage', 'koib_percentage', 'independent_percentage'
    ]
    list_editable = ['ballot_box_votes', 'koib_votes', 'independent_votes']  # Редактирование прямо в списке
    list_filter = ['uik__number', 'updated_at']
    search_fields = ['uik__number', 'uik__address']
    ordering = ['uik__number']
    
    # Группировка полей для удобства редактирования
    fieldsets = (
        ('УИК', {
            'fields': ('uik',)
        }),
        ('Статистика избирателей', {
            'fields': ('planned_voters_count', 'confirmed_voters_display', 'confirmed_percent'),
            'classes': ('collapse',)
        }),
        ('Результаты голосования', {
            'fields': (
                ('ballot_box_votes', 'koib_votes', 'independent_votes'),
            )
        }),
        ('Статистика (только для чтения)', {
            'fields': (
                'total_votes_display', 'percentages_display'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['planned_voters_count', 'confirmed_voters_display', 'confirmed_percent', 'total_votes_display', 'percentages_display']
    
    formats = [XLSX, CSV]

    @display(description='Плановое число')
    def planned_voters_count(self, obj):
        return obj.uik.planned_voters_count

    @display(description='% учтённых')
    def confirmed_percent(self, obj):
        planned = obj.uik.planned_voters_count
        confirmed = obj.confirmed_voters_count
        if planned:
            percent = confirmed / planned * 100
            return f"{percent:.1f}%"
        return "-"

    def has_view_permission(self, request, obj=None):
        """Разрешения на просмотр"""
        return request.user.has_perm('elections.view_uikresults')
    
    def has_add_permission(self, request):
        """Запрещаем ручное добавление - создается автоматически при создании УИК"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_uikresults')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_uikresults')
    
    @display(description='К-во учтенных')
    def confirmed_voters_count(self, obj):
        count = obj.confirmed_voters_count
        return format_html('<strong style="color: blue;">{}</strong>', count)
    
    @display(description='Всего голосов')
    def total_votes(self, obj):
        return obj.total_votes
    
    @display(description='Урна %')
    def ballot_box_percentage(self, obj):
        return f"{obj.ballot_box_percentage}%"
    
    @display(description='КОИБ %')
    def koib_percentage(self, obj):
        return f"{obj.koib_percentage}%"
    
    @display(description='Самост. %')
    def independent_percentage(self, obj):
        return f"{obj.independent_percentage}%"
    
    @display(description='Количество учтенных избирателей')
    def confirmed_voters_display(self, obj):
        count = obj.confirmed_voters_count
        total_registered = obj.uik.voter_set.count()
        percentage = (count / total_registered * 100) if total_registered > 0 else 0
        return format_html(
            'Проголосовало: <strong>{}</strong> из {} зарегистрированных<br>'
            'Явка: <strong>{:.1f}%</strong>',
            count, total_registered, percentage
        )
    
    @display(description='Всего голосов')
    def total_votes_display(self, obj):
        return obj.total_votes
    
    @display(description='Проценты')
    def percentages_display(self, obj):
        return format_html(
            "Урна: <strong>{}%</strong><br>"
            "КОИБ: <strong>{}%</strong><br>"
            "Самостоятельно: <strong>{}%</strong>",
            obj.ballot_box_percentage,
            obj.koib_percentage,
            obj.independent_percentage
        )


@admin.register(Analytics)
class AnalyticsAdmin(ModelAdmin):
    """Админка для аналитики"""
    
    list_display = ['title', 'created_by', 'created_at', 'data_preview']
    list_filter = ['created_by', 'created_at']
    search_fields = ['title', 'description']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description')
        }),
        ('Данные', {
            'fields': ('data',)
        }),
    )
    
    def has_view_permission(self, request, obj=None):
        """Разрешения на просмотр"""
        return request.user.has_perm('elections.view_analytics')
    
    def has_add_permission(self, request):
        """Разрешение на добавление"""
        return request.user.has_perm('elections.add_analytics')
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_analytics')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_analytics')
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    @display(description='Предпросмотр данных')
    def data_preview(self, obj):
        if obj.data:
            preview = str(obj.data)[:50]
            return f"{preview}..." if len(str(obj.data)) > 50 else preview
        return "Нет данных"


# Сигналы для автоматического создания результатов УИК
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=UIK)
def create_uik_results(sender, instance, created, **kwargs):
    """Автоматически создаем запись результатов при создании УИК"""
    if created:
        UIKResults.objects.create(uik=instance)


# Хелпер для проверки группы
OPERATORS_GROUP = 'Операторы избирателей'
def is_operators_user(user):
    return user.groups.filter(name=OPERATORS_GROUP).exists()
