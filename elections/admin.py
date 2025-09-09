from django.contrib import admin
from django.contrib.admin import RelatedOnlyFieldListFilter, SimpleListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.shortcuts import render
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.sections import TableSection
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from import_export.formats.base_formats import XLSX, CSV, XLS
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import HttpResponseRedirect

from .models import User, UIK, Workplace, Voter, UIKResults, UIKAnalysis, UIKResultsDaily, Analytics, PlannedVoter, VotingRecord


# Секции для Unfold
class VotingRecordSection(TableSection):
    """Секция для отображения записей голосования избирателя"""
    verbose_name = "Записи о голосовании"
    height = 200
    related_name = "plannedvoter_set"
    fields = ["voting_date", "voting_method", "confirmed_by_brigadier", "actions"]
    
    def voting_date(self, instance):
        """Дата голосования"""
        if hasattr(instance, 'votingrecord') and instance.votingrecord:
            if instance.votingrecord.voting_date:
                return instance.votingrecord.voting_date.strftime('%d.%m.%Y')
        return "Не указана"
    voting_date.short_description = "Дата голосования"
    
    def voting_method(self, instance):
        """Способ голосования"""
        if hasattr(instance, 'votingrecord') and instance.votingrecord:
            method_choices = {
                'at_uik': 'В УИК',
                'at_home': 'На дому'
            }
            return method_choices.get(instance.votingrecord.voting_method, instance.votingrecord.voting_method or "Не указан")
        return "Не указан"
    voting_method.short_description = "Способ голосования"
    
    def confirmed_by_brigadier(self, instance):
        """Подтверждено бригадиром"""
        if hasattr(instance, 'votingrecord') and instance.votingrecord:
            if instance.votingrecord.confirmed_by_brigadier:
                return format_html('<span style="color: green;">✓ Да</span>')
            else:
                return format_html('<span style="color: red;">❌ Нет</span>')
        return format_html('<span style="color: gray;">—</span>')
    confirmed_by_brigadier.short_description = "Подтверждено бригадиром"
    
    def actions(self, instance):
        """Действия"""
        if hasattr(instance, 'votingrecord') and instance.votingrecord and instance.votingrecord.pk:
            url = reverse('admin:elections_votingrecord_change', args=[instance.votingrecord.pk])
            return format_html('<a href="{}" target="_blank" style="color: #007bff; text-decoration: none;">Открыть</a>', url)
        return "—"
    actions.short_description = "Действия"


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
class UserResource(resources.ModelResource):
    """Ресурс для импорта-экспорта пользователей"""
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'last_name', 'first_name', 'middle_name', 
            'phone_number', 'email', 'role', 'workplace', 
            'is_active_participant', 'is_active'
        )
        export_order = (
            'id', 'username', 'last_name', 'first_name', 'middle_name', 
            'phone_number', 'email', 'role', 'workplace', 
            'is_active_participant', 'is_active'
        )
        import_id_fields = ('username',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    def get_export_headers(self, selected_fields=None):
        """Русские заголовки для экспорта"""
        if selected_fields is not None:
            return super().get_export_headers(selected_fields=selected_fields)
        return [
            'ID', 'Логин', 'Фамилия', 'Имя', 'Отчество', 'Телефон', 'Email',
            'Роль', 'Место работы', 'Активный участник', 'Активен'
        ]
    
    def before_import_row(self, row, **kwargs):
        """Валидация перед импортом строки"""
        # Проверяем обязательные поля
        if not row.get('username'):
            raise ValidationError("Логин обязателен")
        if not row.get('last_name'):
            raise ValidationError("Фамилия обязательна")
        if not row.get('first_name'):
            raise ValidationError("Имя обязательно")
        if not row.get('phone_number'):
            raise ValidationError("Телефон обязателен")
        
        # Валидация роли
        role = row.get('role', '').lower()
        valid_roles = ['admin', 'brigadier', 'agitator', 'operator', 'analyst']
        if role not in valid_roles:
            raise ValidationError(f"Роль должна быть одной из: {', '.join(valid_roles)}")
        
        # Валидация телефона
        phone = row.get('phone_number', '')
        if phone and (not str(phone).startswith('8') or len(str(phone)) != 11):
            raise ValidationError("Телефон должен быть в формате 8XXXXXXXXXX")
        
        # Обработка места работы
        workplace_value = row.get('workplace', '')
        if workplace_value:
            # Если это число (ID), оставляем как есть
            if str(workplace_value).isdigit():
                try:
                    workplace = Workplace.objects.get(id=int(workplace_value))
                    row['workplace'] = workplace.id
                except Workplace.DoesNotExist:
                    raise ValidationError(f"Место работы с ID '{workplace_value}' не найдено в базе данных")
            else:
                # Если это строка (название), ищем по названию
                try:
                    workplace = Workplace.objects.get(name=workplace_value)
                    row['workplace'] = workplace.id
                except Workplace.DoesNotExist:
                    raise ValidationError(f"Место работы '{workplace_value}' не найдено в базе данных")
    
    def before_save_instance(self, instance, row, **kwargs):
        """Обработка перед сохранением"""
        # Устанавливаем пароль по умолчанию если не задан
        if not instance.password or instance.password == '':
            instance.set_password('password123')  # Пароль по умолчанию
        
        # Устанавливаем активность по умолчанию
        if instance.is_active is None:
            instance.is_active = True
        if instance.is_active_participant is None:
            instance.is_active_participant = True
            
        return instance


class WorkplaceResource(resources.ModelResource):
    """Ресурс для импорта-экспорта мест работы"""
    
    class Meta:
        model = Workplace
        fields = ('id', 'name', 'group', 'created_at')
        export_order = ('id', 'name', 'group', 'created_at')
        import_id_fields = ('name',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    def get_export_headers(self, selected_fields=None):
        """Русские заголовки для экспорта"""
        if selected_fields is not None:
            return super().get_export_headers(selected_fields=selected_fields)
        return ['ID', 'Название организации', 'Группа', 'Дата создания']
    
    def before_import_row(self, row, **kwargs):
        """Валидация перед импортом строки"""
        # Проверяем обязательные поля
        if not row.get('name'):
            raise ValidationError("Название организации обязательно")
        
        # Валидация группы
        group = row.get('group', '').lower()
        valid_groups = ['medicine', 'education', 'social_protection', 'agitators', 'other']
        if group and group not in valid_groups:
            raise ValidationError(f"Группа должна быть одной из: {', '.join(valid_groups)}")
        
        # Если группа не указана, устанавливаем по умолчанию
        if not group:
            row['group'] = 'other'
    
    def before_save_instance(self, instance, row, **kwargs):
        """Обработка перед сохранением"""
        # Устанавливаем группу по умолчанию если не задана
        if not instance.group:
            instance.group = 'other'
        return instance


class UIKResource(resources.ModelResource):
    """Ресурс для импорта-экспорта УИК"""
    
    class Meta:
        model = UIK
        fields = ('id', 'number', 'address', 'planned_voters_count', 'brigadier', 'agitators')
        export_order = ('id', 'number', 'address', 'planned_voters_count', 'brigadier', 'agitators')
        import_id_fields = ('number',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    def get_export_headers(self, selected_fields=None):
        """Русские заголовки для экспорта"""
        if selected_fields is not None:
            return super().get_export_headers(selected_fields=selected_fields)
        return ['ID', 'Номер УИК', 'Адрес', 'Плановое количество избирателей', 'Бригадир', 'Агитаторы', 'Дата создания']
    
    def before_import_row(self, row, **kwargs):
        """Валидация перед импортом строки"""
        # Проверяем обязательные поля
        if not row.get('number'):
            raise ValidationError("Номер УИК обязателен")
        if not row.get('address'):
            raise ValidationError("Адрес обязателен")
        
        # Обработка бригадира
        brigadier_value = row.get('brigadier', '')
        if brigadier_value:
            # Если это число (ID), оставляем как есть
            if str(brigadier_value).isdigit():
                try:
                    brigadier = User.objects.get(id=int(brigadier_value), role='brigadier')
                    row['brigadier'] = brigadier.id
                except User.DoesNotExist:
                    raise ValidationError(f"Бригадир с ID '{brigadier_value}' не найден или не является бригадиром")
            else:
                # Если это строка (логин), ищем по логину
                try:
                    brigadier = User.objects.get(username=brigadier_value, role='brigadier')
                    row['brigadier'] = brigadier.id
                except User.DoesNotExist:
                    raise ValidationError(f"Бригадир с логином '{brigadier_value}' не найден или не является бригадиром")
        
        # Обработка агитаторов (через запятую)
        agitators_value = row.get('agitators', '')
        if agitators_value:
            agitator_ids = []
            # Разделяем по запятой
            agitator_identifiers = [x.strip() for x in str(agitators_value).split(',') if x.strip()]
            
            for identifier in agitator_identifiers:
                # Если это число (ID), ищем по ID
                if str(identifier).isdigit():
                    try:
                        agitator = User.objects.get(id=int(identifier), role='agitator')
                        agitator_ids.append(agitator.id)
                    except User.DoesNotExist:
                        raise ValidationError(f"Агитатор с ID '{identifier}' не найден или не является агитатором")
                else:
                    # Если это строка (логин), ищем по логину
                    try:
                        agitator = User.objects.get(username=identifier, role='agitator')
                        agitator_ids.append(agitator.id)
                    except User.DoesNotExist:
                        raise ValidationError(f"Агитатор с логином '{identifier}' не найден или не является агитатором")
            
            row['agitators'] = ','.join(map(str, agitator_ids))
    
    def before_save_instance(self, instance, row, **kwargs):
        """Обработка перед сохранением"""
        # Обрабатываем агитаторов после создания/обновления УИК
        agitators_value = row.get('agitators', '')
        if agitators_value:
            agitator_ids = [int(x) for x in str(agitators_value).split(',') if x.strip()]
            instance.agitators.set(agitator_ids)
        
        return instance


class VoterResource(resources.ModelResource):
    """Ресурс для импорта-экспорта избирателей"""
    
    class Meta:
        model = Voter
        fields = ('id', 'last_name', 'first_name', 'middle_name', 'birth_date', 'registration_address', 'phone_number', 'workplace', 'uik', 'created_at')
        export_order = ('id', 'last_name', 'first_name', 'middle_name', 'birth_date', 'registration_address', 'phone_number', 'workplace', 'uik', 'created_at')
        import_id_fields = ('last_name', 'first_name', 'middle_name', 'birth_date')  # Уникальные поля для импорта
        skip_unchanged = True
        report_skipped = True
        
    def get_export_headers(self, selected_fields=None):
        """Русские заголовки для экспорта"""
        if selected_fields is not None:
            return super().get_export_headers(selected_fields=selected_fields)
        return ['ID', 'Фамилия', 'Имя', 'Отчество', 'Дата рождения', 'Адрес регистрации', 'Телефон', 'Место работы', 'УИК', 'Дата создания']


@admin.register(User)
class UserAdmin(ImportExportModelAdmin, BaseUserAdmin, ModelAdmin):
    """Админка для пользователей с ролями и импортом/экспортом"""
    
    # Ресурс для импорта/экспорта
    resource_class = UserResource
    
    # Формы Unfold для правильного стилизования
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    list_display = ['username', 'id', 'get_full_name', 'phone_number', 'role', 'workplace', 'is_active_participant', 'is_active']
    list_filter = ['role', 'is_active_participant', 'is_active', 'workplace']
    search_fields = ['username', 'first_name', 'last_name', 'phone_number', 'email']
    ordering = ['id']
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                ('username',),
                ('last_name', 'first_name', 'middle_name', 'phone_number', 'email')
            )
        }),

        ('Роль участника', {
            'fields': ('role', 'workplace', 'is_active_participant'),
            'description': 'Выберите роль и место работы пользователя.'
        }),
        ('Статус', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Основная информация', {
            'fields': (
                ('username',),
                ('password1', 'password2'),
                ('last_name', 'first_name', 'middle_name', 'phone_number', 'email')
            )
        }),
        ('Роль участника', {
            'fields': ('role', 'workplace'),
            'description': 'Выберите роль и место работы пользователя.'
        }),
        ('Статус', {
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Обработка ошибок при добавлении"""
        try:
            return super().add_view(request, form_url, extra_context)
        except ValidationError as e:
            from django.contrib import messages
            messages.error(request, str(e))
            return self.response_add(request, None, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Обработка ошибок при изменении"""
        try:
            return super().change_view(request, object_id, form_url, extra_context)
        except ValidationError as e:
            from django.contrib import messages
            messages.error(request, str(e))
            return self.response_change(request, None, extra_context)
    
    @display(description='Полное имя')
    def get_full_name(self, obj):
        return obj.get_full_name()
    

    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Кастомизация полей выбора"""
        if db_field.name == 'workplace':
            kwargs['queryset'] = Workplace.objects.all().order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_fieldsets(self, request, obj=None):
        """Переопределяем fieldsets для добавления полей пароля при редактировании"""
        if not obj:  # Создание нового пользователя
            return self.add_fieldsets
        else:  # Редактирование существующего пользователя
            fieldsets = list(self.fieldsets)
            # Добавляем секцию для изменения пароля
            fieldsets.insert(1, ('Пароль', {
                'fields': ('password',),
                'classes': ('collapse',),
                'description': 'Оставьте пустым, чтобы не изменять пароль'
            }))
            return fieldsets
    



@admin.register(UIK)
class UIKAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для УИК с импортом-экспортом"""
    
    resource_class = UIKResource
    list_display = ['number', 'address_short', 'brigadier', 'agitators_count', 'planned_voters_count', 'actual_voters_count', 'voters_difference', 'has_results']
    list_filter = ['created_at']
    search_fields = ['number', 'address']
    ordering = ['number']
    readonly_fields = ['created_by', 'updated_by', 'created_at', 'updated_at']
    filter_horizontal = ['agitators']
    
    # Поля для редактирования
    fieldsets = (
        ('Основная информация', {
            'fields': ('number', 'address', 'planned_voters_count')
        }),
        ('Персонал', {
            'fields': ('brigadier', 'agitators'),
            'description': 'Назначьте бригадира и агитаторов для УИК'
        }),
        ('Системная информация', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    # Кастомные действия
    actions = ['transfer_agitator_voters', 'remove_agitator_safely']
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_view_permission(self, request, obj=None):
        """Ограничение просмотра списка для обычных пользователей"""
        # Суперпользователи и staff видят все
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Операторы видят все УИК
        if request.user.role == 'operator':
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
    
    @display(description='Агитаторов')
    def agitators_count(self, obj):
        return obj.agitators.count()
    
    def changelist_view(self, request, extra_context=None):
        """Кастомная обработка changelist с уведомлением о правах"""
        if not self.has_view_permission(request):
            from django.contrib import messages
            from django.utils.html import format_html
            messages.error(
                request,
                format_html(
                    '<div style="text-align: center; padding: 15px; background: #ffebee; border: 1px solid #f44336; border-radius: 4px; margin: 10px 0;">'
                    '<h4 style="color: #d32f2f; margin: 0 0 10px 0;">⚠️ Недостаточно прав</h4>'
                    '<p style="color: #666; margin: 0; font-size: 14px;">'
                    'У вас нет прав для просмотра списка УИК. Обратитесь к администратору.'
                    '</p>'
                    '</div>'
                )
            )
            return self.response_post_save_change(request, None)
        return super().changelist_view(request, extra_context)


@admin.register(Workplace)
class WorkplaceAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для мест работы с импортом-экспортом"""
    
    resource_class = WorkplaceResource
    list_display = ['name', 'id', 'group', 'workers_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ['created_by', 'updated_by', 'created_at']
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_view_permission(self, request, obj=None):
        """Ограничение просмотра списка для обычных пользователей"""
        # Суперпользователи и staff видят все
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Операторы видят все места работы
        if request.user.role == 'operator':
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
    
    def changelist_view(self, request, extra_context=None):
        """Кастомная обработка changelist с уведомлением о правах"""
        if not self.has_view_permission(request):
            from django.contrib import messages
            from django.utils.html import format_html
            messages.error(
                request,
                format_html(
                    '<div style="text-align: center; padding: 15px; background: #ffebee; border: 1px solid #f44336; border-radius: 4px; margin: 10px 0;">'
                    '<h4 style="color: #d32f2f; margin: 0 0 10px 0;">⚠️ Недостаточно прав</h4>'
                    '<p style="color: #666; margin: 0; font-size: 14px;">'
                    'У вас нет прав для просмотра списка мест работы. Обратитесь к администратору.'
                    '</p>'
                    '</div>'
                )
            )
            return self.response_post_save_change(request, None)
        return super().changelist_view(request, extra_context)


@admin.register(Voter)
class VoterAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для избирателей с импортом-экспортом"""
    
    resource_class = VoterResource
    list_display = [
        'get_full_name', 'age', 'uik', 'phone_number', 'workplace'
    ]
    list_filter = [
        'uik', 'workplace', 'birth_date',
    ]
    search_fields = [
        'first_name', 'last_name', 'middle_name', 
        'phone_number', 'registration_address'
    ]
    ordering = ['last_name', 'first_name']
    readonly_fields = ['created_by', 'updated_by', 'created_at', 'updated_at', 'age_display']
    
    # Секции для отображения связанных данных
    list_sections = [VotingRecordSection]
    
    # Оптимизация запросов для секций
    list_per_page = 20
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    # Используем вкладки для лучшей организации
    fieldsets = (
        ('Персональные данные', {
            'fields': (
                ('last_name', 'first_name', 'middle_name', 'birth_date'),
                ('phone_number','workplace'),
                'registration_address',
                'uik'
            ),            
            'classes': ('tab',)
        }),
        ('Системная информация', {
            'fields': (
                ('created_by', 'created_at'),
                ('updated_by', 'updated_at')
            ),
            'classes': ('tab', 'collapse')
        }),
    )
    
    # Добавляем кастомные поля для отображения
    def age_display(self, obj):
        """Отображение возраста"""
        return f"{obj.age} лет"
    age_display.short_description = 'Возраст'
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
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
    


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Админ видит все записи
        if request.user.is_superuser or request.user.role == 'admin':
            qs = qs
        # Бригадир видит избирателей своего УИК
        elif request.user.role == 'brigadier':
            uik = UIK.objects.filter(brigadier=request.user).first()
            if uik:
                qs = qs.filter(uik=uik)
            else:
                qs = qs.none()
        # Агитатор видит избирателей своего УИК
        elif request.user.role == 'agitator':
            uik = UIK.objects.filter(agitators=request.user).first()
            if uik:
                qs = qs.filter(uik=uik)
            else:
                qs = qs.none()
        # Оператор видит всех избирателей
        elif request.user.role == 'operator':
            qs = qs
        # По умолчанию - только свои записи
        else:
            qs = qs.filter(created_by=request.user)
        
        # Оптимизация запросов для секций
        return qs.prefetch_related(
            'plannedvoter_set__votingrecord',
            'uik',
            'workplace'
        )

    def has_change_permission(self, request, obj=None):
        # Админ может изменять все
        if request.user.is_superuser or request.user.role == 'admin':
            return True
        
        # Остальные роли могут изменять только свои записи
        if obj is None:
            return True
        return obj.created_by == request.user

    def has_delete_permission(self, request, obj=None):
        # Админы и операторы могут удалять
        if request.user.is_superuser or request.user.role in ['admin', 'operator']:
            return True
        
        # Остальные роли не могут удалять
        return False

    def transfer_agitator_voters(self, request, queryset):
        """Массовый перенос избирателей между агитаторами"""
        if queryset.count() != 1:
            messages.error(request, "Выберите только один УИК для переноса избирателей.")
            return
        
        uik = queryset.first()
        
        # Получаем всех агитаторов УИК
        agitators = uik.agitators.all()
        if agitators.count() < 2:
            messages.error(request, "В УИК должно быть минимум 2 агитатора для переноса.")
            return
        
        # Создаем форму для выбора агитаторов
        if request.method == 'POST':
            old_agitator_id = request.POST.get('old_agitator')
            new_agitator_id = request.POST.get('new_agitator')
            
            if old_agitator_id and new_agitator_id:
                old_agitator = User.objects.get(id=old_agitator_id)
                new_agitator = User.objects.get(id=new_agitator_id)
                
                success, message = uik.transfer_agitator_voters(old_agitator, new_agitator, request.user)
                
                if success:
                    messages.success(request, message)
                else:
                    messages.error(request, message)
                
                return HttpResponseRedirect(request.get_full_path())
        
        context = {
            'title': 'Перенос избирателей между агитаторами',
            'uik': uik,
            'agitators': agitators,
            'queryset': queryset,
        }
        
        return render(request, 'admin/transfer_agitator_voters.html', context)
    
    transfer_agitator_voters.short_description = "Перенести избирателей между агитаторами"
    
    def remove_agitator_safely(self, request, queryset):
        """Безопасное удаление агитатора с переносом избирателей"""
        if queryset.count() != 1:
            messages.error(request, "Выберите только один УИК для удаления агитатора.")
            return
        
        uik = queryset.first()
        
        # Получаем всех агитаторов УИК
        agitators = uik.agitators.all()
        if agitators.count() < 2:
            messages.error(request, "В УИК должно быть минимум 2 агитатора для безопасного удаления.")
            return
        
        # Создаем форму для выбора агитатора
        if request.method == 'POST':
            agitator_id = request.POST.get('agitator')
            
            if agitator_id:
                agitator = User.objects.get(id=agitator_id)
                success, message = uik.remove_agitator_safely(agitator, request.user)
                
                if success:
                    messages.success(request, message)
                else:
                    messages.error(request, message)
                
                return HttpResponseRedirect(request.get_full_path())
        
        context = {
            'title': 'Безопасное удаление агитатора',
            'uik': uik,
            'agitators': agitators,
            'queryset': queryset,
        }
        
        return render(request, 'admin/remove_agitator_safely.html', context)
    
    remove_agitator_safely.short_description = "Безопасно удалить агитатора"

    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        
        # Админы имеют все права
        if request.user.is_superuser or request.user.role == 'admin':
            return perms
        
        # Остальные роли могут просматривать, добавлять и изменять
        return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}


@admin.register(UIKResults)
class UIKResultsAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для результатов по УИК с редактированием в списке"""
    
    list_display = [
        'uik', 'planned_voters_count', 'confirmed_voters_count', 'confirmed_percent',
        'at_uik_votes', 'at_home_votes',
        'total_votes', 'at_uik_percentage', 'at_home_percentage'
    ]
    list_editable = ['at_uik_votes', 'at_home_votes']  # Редактирование прямо в списке
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
                ('at_uik_votes', 'at_home_votes'),
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
    
    @display(description='В УИК %')
    def at_uik_percentage(self, obj):
        return f"{obj.at_uik_percentage}%"
    
    @display(description='На дому %')
    def at_home_percentage(self, obj):
        return f"{obj.at_home_percentage}%"
    
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
            "В УИК: <strong>{}%</strong><br>"
            "На дому: <strong>{}%</strong>",
            obj.at_uik_percentage,
            obj.at_home_percentage
        )


@admin.register(UIKAnalysis)
class UIKAnalysisAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для анализа по УИК с редактированием в списке"""
    
    list_display = [
        'uik', 'home_plan', 'home_fact', 'home_execution_percentage',
        'site_plan', 'site_fact', 'site_execution_percentage',
        'total_plan', 'total_fact', 'plan_execution_percentage'
    ]
    list_editable = ['home_plan', 'home_fact', 'site_plan', 'site_fact']  # Редактирование прямо в списке
    list_filter = ['uik__number', 'updated_at']
    search_fields = ['uik__number', 'uik__address']
    ordering = ['uik__number']
    readonly_fields = ['total_plan', 'total_fact', 'plan_execution_percentage', 'home_execution_percentage', 'site_execution_percentage']
    
    # Группировка полей для удобства редактирования
    fieldsets = (
        ('УИК', {
            'fields': ('uik',)
        }),
        ('Планы', {
            'fields': (
                ('home_plan', 'site_plan'),
                'total_plan_display'
            )
        }),
        ('Факты', {
            'fields': (
                ('home_fact', 'site_fact'),
                'total_fact_display'
            )
        }),
        ('Статистика выполнения (только для чтения)', {
            'fields': [
                'execution_percentages_display'
            ],
            'classes': ('collapse',)
        }),
    )
    
    formats = [XLSX, CSV]

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_view_permission(self, request, obj=None):
        """Разрешения на просмотр"""
        return request.user.has_perm('elections.view_uikanalysis')
    
    def has_add_permission(self, request):
        """Запрещаем ручное добавление - создается автоматически при создании УИК"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_uikanalysis')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_uikanalysis')
    
    @display(description='Общий план')
    def total_plan(self, obj):
        return obj.total_plan
    
    @display(description='Общий факт')
    def total_fact(self, obj):
        return obj.total_fact
    
    @display(description='% выполнения')
    def plan_execution_percentage(self, obj):
        percent = obj.plan_execution_percentage
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='% выполнения на дому')
    def home_execution_percentage(self, obj):
        percent = obj.home_execution_percentage
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='% выполнения на участке')
    def site_execution_percentage(self, obj):
        percent = obj.site_execution_percentage
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='Общий план')
    def total_plan_display(self, obj):
        return f"{obj.total_plan} голосов"
    
    @display(description='Общий факт')
    def total_fact_display(self, obj):
        return f"{obj.total_fact} голосов"
    
    @display(description='Проценты выполнения')
    def execution_percentages_display(self, obj):
        return format_html(
            "Общий: <strong>{}%</strong><br>"
            "На дому: <strong>{}%</strong><br>"
            "На участке: <strong>{}%</strong>",
            obj.plan_execution_percentage,
            obj.home_execution_percentage,
            obj.site_execution_percentage
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


@admin.register(PlannedVoter)
class PlannedVoterAdmin(ModelAdmin):
    """Админка для планирования избирателей с массовыми операциями"""
    
    # Настройки для отображения в сайдбаре
    verbose_name = 'Планируемый избиратель'
    verbose_name_plural = 'Планируемые избиратели'
    
    list_display = [
        'voter', 'agitator', 'planned_date', 'status_display', 'voting_status_display', 'uik'
    ]
    
    def status_display(self, obj):
        """Красивое отображение статуса планирования"""
        if obj.status == 'planned':
            return format_html('<span style="color: blue;">📋 Запланирован</span>')
        elif obj.status == 'refused':
            return format_html('<span style="color: red;">❌ Отказался</span>')
        elif obj.status == 'voted':
            return format_html('<span style="color: green;">✅ Проголосовал</span>')
        else:
            return format_html('<span style="color: gray;">❓ Неизвестно</span>')
    status_display.short_description = "Статус планирования"
    status_display.admin_order_field = 'status'
    
    def voting_status_display(self, obj):
        return obj.voting_status_display
    voting_status_display.short_description = "Статус голосования"
    voting_status_display.admin_order_field = 'votingrecord__id'
    list_filter = [
        'status', 'agitator', 'planned_date', 'created_at', 'voter__uik',
        ('votingrecord__confirmed_by_brigadier', admin.BooleanFieldListFilter),
        ('votingrecord__voting_method', admin.AllValuesFieldListFilter),
    ]
    search_fields = [
        'voter__first_name', 'voter__last_name', 'voter__middle_name',
        'agitator__first_name', 'agitator__last_name'
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'voting_status_display']
    
    # Массовые операции
    actions = ['confirm_voting', 'set_planned_date', 'create_voting_records', 'set_status_refused']
    
    fieldsets = (
        ('Планирование', {
            'fields': (
                ('voter', 'agitator'),
                'planned_date',
                'notes'
            )
        }),
        ('Статус', {
            'fields': ('status', 'voting_status_display'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': (
                ('created_at', 'updated_at')
            ),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_change_permission(self, request, obj=None):
        """Блокируем изменение если голосование подтверждено"""
        if obj and hasattr(obj, 'votingrecord') and obj.votingrecord.confirmed_by_brigadier:
            return False
        return super().has_change_permission(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        """Делаем поля только для чтения если голосование подтверждено"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and hasattr(obj, 'votingrecord') and obj.votingrecord.confirmed_by_brigadier:
            # Добавляем все поля в readonly если голосование подтверждено
            readonly_fields.extend(['voter', 'agitator', 'planned_date', 'notes', 'status'])
        return readonly_fields
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Кастомизация полей выбора на основе роли пользователя"""
        if db_field.name == 'voter':
            # Получаем ID текущего избирателя (если редактируем существующую запись)
            current_voter_id = None
            if 'object_id' in request.resolver_match.kwargs:
                try:
                    planned_voter = PlannedVoter.objects.get(id=request.resolver_match.kwargs['object_id'])
                    current_voter_id = planned_voter.voter_id
                except PlannedVoter.DoesNotExist:
                    pass
            
            # Исключаем избирателей, которые уже в списке планируемых, НО включаем текущего
            existing_voter_ids = PlannedVoter.objects.values_list('voter_id', flat=True)
            if current_voter_id:
                existing_voter_ids = [vid for vid in existing_voter_ids if vid != current_voter_id]
            
            # Для агитаторов показываем только избирателей их УИК
            if request.user.role == 'agitator':
                uik = UIK.objects.filter(agitators=request.user).first()
                if uik:
                    kwargs['queryset'] = Voter.objects.filter(
                        uik=uik
                    ).exclude(
                        id__in=existing_voter_ids
                    ).order_by('last_name', 'first_name')
            # Для бригадиров показываем только избирателей их УИК
            elif request.user.role == 'brigadier':
                uik = UIK.objects.filter(brigadier=request.user).first()
                if uik:
                    kwargs['queryset'] = Voter.objects.filter(
                        uik=uik
                    ).exclude(
                        id__in=existing_voter_ids
                    ).order_by('last_name', 'first_name')
            # Для админов и операторов показываем всех избирателей
            elif request.user.is_superuser or request.user.role in ['admin', 'operator']:
                kwargs['queryset'] = Voter.objects.exclude(
                    id__in=existing_voter_ids
                ).order_by('last_name', 'first_name')
            else:
                kwargs['queryset'] = Voter.objects.none()
        elif db_field.name == 'agitator':
            # Если пользователь админ - показываем всех агитаторов
            if request.user.is_superuser or request.user.role == 'admin':
                kwargs['queryset'] = User.objects.filter(
                    role='agitator',
                    is_active_participant=True
                ).order_by('last_name', 'first_name')
            # Если пользователь бригадир или агитатор - показываем только агитаторов их УИК
            elif request.user.role in ['brigadier', 'agitator']:
                # Получаем УИК пользователя
                user_uiks = []
                if request.user.role == 'brigadier':
                    user_uiks = UIK.objects.filter(brigadier=request.user)
                elif request.user.role == 'agitator':
                    user_uiks = UIK.objects.filter(agitators=request.user)
                
                if user_uiks.exists():
                    kwargs['queryset'] = User.objects.filter(
                        role='agitator',
                        is_active_participant=True,
                        assigned_uiks_as_agitator__in=user_uiks
                    ).order_by('last_name', 'first_name')
                else:
                    kwargs['queryset'] = User.objects.none()
            # Для операторов - показываем агитаторов на основе выбранного УИК в избирателе
            elif request.user.role == 'operator':
                # Получаем УИК из выбранного избирателя (если есть)
                voter_id = request.GET.get('voter') or request.POST.get('voter')
                if voter_id:
                    try:
                        voter = Voter.objects.get(id=voter_id)
                        kwargs['queryset'] = User.objects.filter(
                            role='agitator',
                            is_active_participant=True,
                            assigned_uiks_as_agitator=voter.uik
                        ).order_by('last_name', 'first_name')
                    except Voter.DoesNotExist:
                        kwargs['queryset'] = User.objects.none()
                else:
                    # Если избиратель не выбран, показываем всех агитаторов
                    kwargs['queryset'] = User.objects.filter(
                        role='agitator',
                        is_active_participant=True
                    ).order_by('last_name', 'first_name')
            else:
                kwargs['queryset'] = User.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    @display(description='УИК')
    def uik(self, obj):
        """Отображение УИК"""
        return f"УИК №{obj.voter.uik.number}"
    
    @display(description='Статус голосования')
    def voting_status(self, obj):
        if obj.has_voting_record:
            record = obj.votingrecord
            if record.is_confirmed:
                return format_html(
                    '<span style="color: green;">✓ Подтверждено</span>'
                )
            elif record.voting_date:
                return format_html(
                    '<span style="color: orange;">📅 {}</span>', 
                    record.voting_date.strftime('%d.%m.%Y')
                )
            else:
                return format_html(
                    '<span style="color: blue;">📝 Записано</span>'
                )
        else:
            return format_html(
                '<span style="color: gray;">❌ Не записано</span>'
            )
    
    def voting_status_display(self, obj):
        if obj.has_voting_record:
            record = obj.votingrecord
            if record.is_confirmed:
                return format_html('<span style="color: green;">✅ Проголосовал</span>')
            elif record.voting_date:
                return format_html('<span style="color: orange;">📅 {}</span>', record.voting_date.strftime('%d.%m.%Y'))
            else:
                return format_html('<span style="color: blue;">📝 Записано</span>')
        else:
            return format_html('<span style="color: gray;">⏳ Ожидает голосования</span>')
    voting_status_display.short_description = "Статус голосования"
    voting_status_display.admin_order_field = 'votingrecord__id'
    
    # Массовые операции
    @admin.action(description='Подтвердить голосование')
    def confirm_voting(self, request, queryset):
        """Массовое подтверждение голосования бригадиром"""
        updated = 0
        for planned_voter in queryset:
            if planned_voter.has_voting_record:
                record = planned_voter.votingrecord
                if record.voting_date and not record.confirmed_by_brigadier:
                    record.confirmed_by_brigadier = True
                    record.save()
                    updated += 1
        
        self.message_user(
            request, 
            f'Подтверждено голосование для {updated} избирателей'
        )
    
    @admin.action(description='Установить планируемую дату')
    def set_planned_date(self, request, queryset):
        """Массовая установка планируемой даты"""
        from django import forms
        
        class DateForm(forms.Form):
            planned_date = forms.DateField(label='Планируемая дата')
        
        if 'apply' in request.POST:
            form = DateForm(request.POST)
            if form.is_valid():
                date = form.cleaned_data['planned_date']
                updated = queryset.update(planned_date=date)
                self.message_user(
                    request, 
                    f'Установлена планируемая дата для {updated} избирателей'
                )
                return
        else:
            form = DateForm()
        
        return render(
            request,
            'admin/plannedvoter/set_date.html',
            context={
                'form': form,
                'queryset': queryset,
                'opts': self.model._meta,
                'action': 'set_planned_date'
            }
        )
    
    @admin.action(description='Создать записи о голосовании')
    def create_voting_records(self, request, queryset):
        """Массовое создание записей о голосовании"""
        created = 0
        for planned_voter in queryset:
            if not planned_voter.has_voting_record:
                VotingRecord.objects.create(planned_voter=planned_voter)
                created += 1
        
        self.message_user(
            request, 
            f'Создано {created} записей о голосовании'
        )
    
    @admin.action(description='Отметить как отказавшихся')
    def set_status_refused(self, request, queryset):
        """Массовое изменение статуса на 'Отказался'"""
        updated = queryset.update(status='refused')
        self.message_user(
            request, 
            f'Статус изменен на "Отказался" для {updated} избирателей'
        )
    

    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Админ видит все записи
        if request.user.is_superuser or request.user.role == 'admin':
            return qs
        
        # Бригадир видит записи своего УИК
        elif request.user.role == 'brigadier':
            uik = UIK.objects.filter(brigadier=request.user).first()
            if uik:
                return qs.filter(voter__uik=uik)
            return qs.none()
        
        # Агитатор видит записи своего УИК
        elif request.user.role == 'agitator':
            uik = UIK.objects.filter(agitators=request.user).first()
            if uik:
                return qs.filter(voter__uik=uik)
            return qs.none()
        
        # По умолчанию - только свои записи
        return qs.filter(created_by=request.user)
    
    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        
        # Админы имеют все права
        if request.user.is_superuser or request.user.role == 'admin':
            return perms
        
        # Бригадиры и агитаторы могут просматривать, добавлять и изменять
        elif request.user.role in ['brigadier', 'agitator']:
            return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}
        
        # Операторы могут просматривать, добавлять и изменять
        elif request.user.role == 'operator':
            return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}
        
        # Операторы избирателей (старая логика)
        elif is_operators_user(request.user):
            return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}
        
        # По умолчанию - только просмотр и добавление
        return {'add': perms['add'], 'view': perms['view']}
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Показываем предупреждение если запись заблокирована"""
        obj = self.get_object(request, object_id)
        if obj and hasattr(obj, 'votingrecord') and obj.votingrecord.confirmed_by_brigadier:
            from django.contrib import messages
            messages.warning(
                request,
                '⚠️ Эта запись заблокирована для редактирования, так как голосование подтверждено бригадиром. '
                'Для разблокировки снимите отметку подтверждения в записи о голосовании.'
            )
        return super().change_view(request, object_id, form_url, extra_context)
    
    def changelist_view(self, request, extra_context=None):
        """Обработка AJAX запросов для получения агитаторов"""
        if request.GET.get('ajax') == 'get_agitators':
            from django.http import JsonResponse
            voter_id = request.GET.get('voter')
            
            if voter_id:
                try:
                    voter = Voter.objects.get(id=voter_id)
                    agitators = User.objects.filter(
                        role='agitator',
                        is_active_participant=True,
                        assigned_uiks_as_agitator=voter.uik
                    ).values('id', 'last_name', 'first_name', 'middle_name')
                    
                    agitators_data = []
                    for agitator in agitators:
                        agitators_data.append({
                            'id': agitator['id'],
                            'full_name': f"{agitator['last_name']} {agitator['first_name']} {agitator['middle_name']}".strip()
                        })
                    
                    return JsonResponse({'agitators': agitators_data})
                except Voter.DoesNotExist:
                    return JsonResponse({'agitators': []})
            
            return JsonResponse({'agitators': []})
        
        return super().changelist_view(request, extra_context)


@admin.register(VotingRecord)
class VotingRecordAdmin(ModelAdmin):
    """Админка для записей о голосовании с массовыми операциями"""
    
    # Настройки для отображения в сайдбаре
    verbose_name = 'Запись о голосовании'
    verbose_name_plural = 'Записи о голосовании'
    
    list_display = [
        'voter', 'agitator', 'voting_date', 'voting_method', 
        'confirmed_by_brigadier', 'uik'
    ]
    list_filter = [
        'voting_date', 'voting_method', 'confirmed_by_brigadier',
        'planned_voter__agitator', 'created_at'
    ]
    list_editable = ['voting_date', 'voting_method', 'confirmed_by_brigadier']
    search_fields = [
        'planned_voter__voter__first_name', 'planned_voter__voter__last_name',
        'planned_voter__agitator__first_name', 'planned_voter__agitator__last_name'
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'is_confirmed_display']
    
    # Массовые операции
    actions = ['confirm_voting', 'set_voting_date', 'set_voting_method']
    
    fieldsets = (
        ('Голосование', {
            'fields': (
                'planned_voter',
                ('voting_date', 'voting_method'),
                ('confirmed_by_brigadier', 'is_confirmed_display')
            )
        }),
        ('Заметки', {
            'fields': ('brigadier_notes',)
        }),
        ('Системная информация', {
            'fields': (
                ('created_at', 'updated_at')
            ),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_fieldsets(self, request, obj=None):
        """Динамически изменяем поля в зависимости от роли пользователя"""
        if request.user.role == 'agitator':
            # Агитатор может заполнять дату голосования и способ
            return (
                ('Голосование', {
                    'fields': (
                        'planned_voter',
                        ('voting_date', 'voting_method'),
                    )
                }),
                ('Системная информация', {
                    'fields': (
                        ('created_at', 'updated_at')
                    ),
                    'classes': ('collapse',)
                }),
            )
        elif request.user.role == 'brigadier':
            # Бригадир может заполнять дату, способ и подтверждение
            return (
                ('Голосование', {
                    'fields': (
                        'planned_voter',
                        ('voting_date', 'voting_method'),
                        'confirmed_by_brigadier'
                    )
                }),
                ('Заметки', {
                    'fields': ('brigadier_notes',)
                }),
                ('Системная информация', {
                    'fields': (
                        ('created_at', 'updated_at')
                    ),
                    'classes': ('collapse',)
                }),
            )
        else:
            # Админ видит все поля
            return self.fieldsets
    
    @display(description='Избиратель')
    def voter(self, obj):
        return obj.planned_voter.voter
    
    @display(description='Агитатор')
    def agitator(self, obj):
        return obj.planned_voter.agitator
    
    @display(description='УИК')
    def uik(self, obj):
        """Отображение УИК"""
        return f"УИК №{obj.planned_voter.voter.uik.number}"
    
    @display(description='Подтверждено')
    def is_confirmed_display(self, obj):
        if obj.is_confirmed:
            return format_html(
                '<span style="color: green;">✓ Подтверждено</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">❌ Не подтверждено</span>'
            )
    
    # Массовые операции
    @admin.action(description='Подтвердить голосование')
    def confirm_voting(self, request, queryset):
        """Массовое подтверждение голосования"""
        updated = queryset.update(confirmed_by_brigadier=True)
        self.message_user(
            request, 
            f'Подтверждено голосование для {updated} избирателей'
        )
    
    @admin.action(description='Установить дату голосования')
    def set_voting_date(self, request, queryset):
        """Массовая установка даты голосования"""
        from django import forms
        
        class DateForm(forms.Form):
            voting_date = forms.DateField(label='Дата голосования')
        
        if 'apply' in request.POST:
            form = DateForm(request.POST)
            if form.is_valid():
                date = form.cleaned_data['voting_date']
                updated = queryset.update(voting_date=date)
                self.message_user(
                    request, 
                    f'Установлена дата голосования для {updated} избирателей'
                )
                return
        else:
            form = DateForm()
        
        return render(
            request,
            'admin/votingrecord/set_date.html',
            context={
                'form': form,
                'queryset': queryset,
                'opts': self.model._meta,
                'action': 'set_voting_date'
            }
        )
    
    @admin.action(description='Установить способ голосования')
    def set_voting_method(self, request, queryset):
        """Массовая установка способа голосования"""
        from django import forms
        
        class MethodForm(forms.Form):
            voting_method = forms.ChoiceField(
                label='Способ голосования',
                choices=[
                    ('at_uik', 'В УИК'),
                    ('at_home', 'На дому'),
                ]
            )
        
        if 'apply' in request.POST:
            form = MethodForm(request.POST)
            if form.is_valid():
                method = form.cleaned_data['voting_method']
                updated = queryset.update(voting_method=method)
                self.message_user(
                    request, 
                    f'Установлен способ голосования для {updated} избирателей'
                )
                return
        else:
            form = MethodForm()
        
        return render(
            request,
            'admin/votingrecord/set_method.html',
            context={
                'form': form,
                'queryset': queryset,
                'opts': self.model._meta,
                'action': 'set_voting_method'
            }
        )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Исключаем записи для отказавшихся избирателей
        qs = qs.exclude(planned_voter__status='refused')
        
        # Админ видит все записи
        if request.user.is_superuser or request.user.role == 'admin':
            return qs
        
        # Бригадир видит записи своего УИК
        elif request.user.role == 'brigadier':
            uik = UIK.objects.filter(brigadier=request.user).first()
            if uik:
                return qs.filter(planned_voter__voter__uik=uik)
            return qs.none()
        
        # Агитатор видит записи своего УИК
        elif request.user.role == 'agitator':
            uik = UIK.objects.filter(agitators=request.user).first()
            if uik:
                return qs.filter(planned_voter__voter__uik=uik)
            return qs.none()
        
        # По умолчанию - только свои записи
        return qs.filter(created_by=request.user)
    
    def get_model_perms(self, request):
        perms = super().get_model_perms(request)
        
        # Админы имеют все права
        if request.user.is_superuser or request.user.role == 'admin':
            return perms
        
        # Бригадиры и агитаторы могут только просматривать и изменять (не добавлять/удалять)
        elif request.user.role in ['brigadier', 'agitator']:
            return {'change': perms['change'], 'view': perms['view']}
        
        # Операторы могут только просматривать и изменять (не добавлять/удалять)
        elif request.user.role == 'operator':
            return {'change': perms['change'], 'view': perms['view']}
        
        # Операторы избирателей (старая логика)
        elif is_operators_user(request.user):
            return {'add': perms['add'], 'change': perms['change'], 'view': perms['view']}
        
        # По умолчанию - только просмотр
        return {'view': perms['view']}
    
    def has_add_permission(self, request):
        """Запрещаем ручное добавление записей о голосовании"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление записей о голосовании только админам и операторам"""
        return request.user.is_superuser or request.user.role in ['admin', 'operator']


# Хелпер для проверки группы
OPERATORS_GROUP = 'Операторы избирателей'
def is_operators_user(user):
    return user.groups.filter(name=OPERATORS_GROUP).exists()


@admin.register(UIKResultsDaily)
class UIKResultsDailyAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для результатов по дням УИК с редактированием в списке"""
    
    list_display = [
        'uik', 'total_plan', 'total_fact', 'plan_execution_percentage',
        'separator_1',
        'plan_12_sep', 'fact_12_sep', 'fact_12_sep_calculated', 'fact_12_sep_locked', 'plan_12_percent',
        'separator_2',
        'plan_13_sep', 'fact_13_sep', 'fact_13_sep_calculated', 'fact_13_sep_locked', 'plan_13_percent', 
        'separator_3',
        'plan_14_sep', 'fact_14_sep', 'fact_14_sep_calculated', 'fact_14_sep_locked', 'plan_14_percent'
    ]
    list_editable = [
        'plan_12_sep', 'plan_13_sep', 'plan_14_sep', 
        'fact_12_sep', 'fact_13_sep', 'fact_14_sep',
        'fact_12_sep_locked', 'fact_13_sep_locked', 'fact_14_sep_locked'
    ]  # Редактирование прямо в списке
    list_filter = ['uik__number', 'updated_at']
    search_fields = ['uik__number', 'uik__address']
    ordering = ['uik__number']
    readonly_fields = ['total_fact', 'plan_execution_percentage', 'plan_12_percent', 'plan_13_percent', 'plan_14_percent', 'fact_12_sep_calculated', 'fact_13_sep_calculated', 'fact_14_sep_calculated', 'separator_1', 'separator_2', 'separator_3', 'created_by', 'updated_by', 'created_at', 'updated_at']
    
    # Группировка полей для удобства редактирования
    fieldsets = (
        ('УИК', {
            'fields': ('uik',)
        }),
        ('Планы по дням', {
            'fields': (
                ('plan_12_sep', 'plan_13_sep', 'plan_14_sep'),
            ),
            'description': 'Плановое количество голосов по дням голосования'
        }),
        ('Факты по дням (ручные)', {
            'fields': (
                ('fact_12_sep', 'fact_13_sep', 'fact_14_sep'),
            ),
            'description': 'Фактическое количество голосов по дням голосования (ручное введение)'
        }),
        ('Расчетные факты (только для чтения)', {
            'fields': (
                ('fact_12_sep_calculated', 'fact_13_sep_calculated', 'fact_14_sep_calculated'),
            ),
            'description': 'Автоматически рассчитываемые факты по дням',
            'classes': ('collapse',)
        }),
        ('Управление фактами 12.09', {
            'fields': (
                ('fact_12_sep_locked', 'fact_12_sep_source'),
            ),
            'description': 'Настройки для 12 сентября',
            'classes': ('collapse',)
        }),
        ('Управление фактами 13.09', {
            'fields': (
                ('fact_13_sep_locked', 'fact_13_sep_source'),
            ),
            'description': 'Настройки для 13 сентября',
            'classes': ('collapse',)
        }),
        ('Управление фактами 14.09', {
            'fields': (
                ('fact_14_sep_locked', 'fact_14_sep_source'),
            ),
            'description': 'Настройки для 14 сентября',
            'classes': ('collapse',)
        }),
    )
    
    formats = [XLSX, CSV]

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем создателя/редактора"""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_view_permission(self, request, obj=None):
        """Разрешения на просмотр"""
        return request.user.has_perm('elections.view_uikresultsdaily')
    
    def has_add_permission(self, request):
        """Запрещаем ручное добавление - создается автоматически при создании УИК"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Разрешение на изменение"""
        return request.user.has_perm('elections.change_uikresultsdaily')
    
    def has_delete_permission(self, request, obj=None):
        """Разрешение на удаление"""
        return request.user.has_perm('elections.delete_uikresultsdaily')
    
    @display(description='План 12.09')
    def plan_12_sep_display(self, obj):
        return format_html('<strong style="color: orange;">{}</strong>', obj.plan_12_sep)
    
    @display(description='План 13.09')
    def plan_13_sep_display(self, obj):
        return format_html('<strong style="color: orange;">{}</strong>', obj.plan_13_sep)
    
    @display(description='План 14.09')
    def plan_14_sep_display(self, obj):
        return format_html('<strong style="color: orange;">{}</strong>', obj.plan_14_sep)
    
    
    @display(description='План')
    def total_plan(self, obj):
        return format_html('<strong style="color: orange;">{}</strong>', obj.total_plan)
    
    @display(description='Факт')
    def total_fact(self, obj):
        return format_html('<strong style="color: green;">{}</strong>', obj.total_fact)
    
    @display(description='%')
    def plan_execution_percentage(self, obj):
        percent = obj.plan_execution_percentage
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='Общий план')
    def total_plan_display(self, obj):
        return f"{obj.total_plan} голосов"
    
    @display(description='Общий факт')
    def total_fact_display(self, obj):
        return f"{obj.total_fact} голосов"
    
    @display(description='')
    def separator_1(self, obj):
        return format_html('<div style="border-left: 3px solid #ddd; height: 30px; margin: 0 8px; background: #f8f9fa;"></div>')
    
    @display(description='')
    def separator_2(self, obj):
        return format_html('<div style="border-left: 3px solid #ddd; height: 30px; margin: 0 8px; background: #f8f9fa;"></div>')
    
    @display(description='')
    def separator_3(self, obj):
        return format_html('<div style="border-left: 3px solid #ddd; height: 30px; margin: 0 8px; background: #f8f9fa;"></div>')
    
    @display(description='% 12.09')
    def plan_12_percent(self, obj):
        effective_fact = obj.get_effective_fact_12_sep()
        percent = round((effective_fact / obj.plan_12_sep * 100), 1) if obj.plan_12_sep > 0 else 0
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='% 13.09')
    def plan_13_percent(self, obj):
        effective_fact = obj.get_effective_fact_13_sep()
        percent = round((effective_fact / obj.plan_13_sep * 100), 1) if obj.plan_13_sep > 0 else 0
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='% 14.09')
    def plan_14_percent(self, obj):
        effective_fact = obj.get_effective_fact_14_sep()
        percent = round((effective_fact / obj.plan_14_sep * 100), 1) if obj.plan_14_sep > 0 else 0
        if percent >= 100:
            color = 'green'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, percent)
    
    @display(description='Расчетный 12.09')
    def fact_12_sep_calculated_display(self, obj):
        return format_html('<strong style="color: blue;">{}</strong>', obj.fact_12_sep_calculated)
    
    @display(description='Расчетный 13.09')
    def fact_13_sep_calculated_display(self, obj):
        return format_html('<strong style="color: blue;">{}</strong>', obj.fact_13_sep_calculated)
    
    @display(description='Расчетный 14.09')
    def fact_14_sep_calculated_display(self, obj):
        return format_html('<strong style="color: blue;">{}</strong>', obj.fact_14_sep_calculated)
    
    @display(description='Процент выполнения')
    def plan_execution_percentage_display(self, obj):
        return format_html(
            "Общий: <strong>{}%</strong><br>"
            "12.09: <strong>{} голосов</strong><br>"
            "13.09: <strong>{} голосов</strong><br>"
            "14.09: <strong>{} голосов</strong>",
            obj.plan_execution_percentage,
            obj.fact_12_sep,
            obj.fact_13_sep,
            obj.fact_14_sep
        )
    
    def get_queryset(self, request):
        """Фильтруем записи в зависимости от роли пользователя"""
        qs = super().get_queryset(request)
        
        # Админы видят все записи
        if request.user.is_superuser or request.user.role == 'admin':
            return qs
        
        # Бригадиры видят только свои УИК
        if request.user.role == 'brigadier':
            return qs.filter(uik__brigadier=request.user)
        
        # Агитаторы видят только УИК где они работают
        if request.user.role == 'agitator':
            return qs.filter(uik__agitators=request.user)
        
        # Остальные роли не видят ничего
        return qs.none()
    
    def has_change_permission(self, request, obj=None):
        # Админы могут изменять все
        if request.user.is_superuser or request.user.role == 'admin':
            return True
        
        # Бригадиры могут изменять только свои УИК
        if request.user.role == 'brigadier' and obj:
            return obj.uik.brigadier == request.user
        
        # Агитаторы могут изменять только УИК где они работают
        if request.user.role == 'agitator' and obj:
            return obj.uik.agitators.filter(id=request.user.id).exists()
        
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Только админы могут удалять
        return request.user.is_superuser or request.user.role == 'admin'
    
    def save_model(self, request, obj, form, change):
        """Автоматически заполняем поля created_by и updated_by и перезаписываем факты"""
        if not change:  # Создание новой записи
            obj.created_by = request.user
        obj.updated_by = request.user
        
        # Сохраняем объект
        super().save_model(request, obj, form, change)
        
        # Перезаписываем fact_XX_sep на эффективные значения если не заблокировано
        if not obj.fact_12_sep_locked:
            obj.fact_12_sep = max(obj.fact_12_sep, obj.fact_12_sep_calculated)
        if not obj.fact_13_sep_locked:
            obj.fact_13_sep = max(obj.fact_13_sep, obj.fact_13_sep_calculated)
        if not obj.fact_14_sep_locked:
            obj.fact_14_sep = max(obj.fact_14_sep, obj.fact_14_sep_calculated)
        
        # Сохраняем обновленные значения
        obj.save(update_fields=['fact_12_sep', 'fact_13_sep', 'fact_14_sep'])
    
    # Действия для массовых операций
    actions = ['recalculate_daily_facts', 'recalculate_all_daily_facts']
    
    def get_changelist_form(self, request, **kwargs):
        """Кастомная форма для changelist с перезаписью fact_XX_sep на эффективные значения"""
        form = super().get_changelist_form(request, **kwargs)
        
        # Переопределяем метод save для формы
        original_save = form.save
        
        def custom_save(*args, **kwargs):
            commit = kwargs.get('commit', True)
            instance = original_save(*args, **kwargs)
            if commit and instance:
                # Перезаписываем fact_XX_sep на эффективные значения если не заблокировано
                if not instance.fact_12_sep_locked:
                    instance.fact_12_sep = max(instance.fact_12_sep, instance.fact_12_sep_calculated)
                if not instance.fact_13_sep_locked:
                    instance.fact_13_sep = max(instance.fact_13_sep, instance.fact_13_sep_calculated)
                if not instance.fact_14_sep_locked:
                    instance.fact_14_sep = max(instance.fact_14_sep, instance.fact_14_sep_calculated)
                
                # Сохраняем обновленные значения
                instance.save(update_fields=['fact_12_sep', 'fact_13_sep', 'fact_14_sep'])
            return instance
        
        form.save = custom_save
        return form
    
    @admin.action(description='Пересчитать факты для выбранных УИК')
    def recalculate_daily_facts(self, request, queryset):
        """Пересчитать расчетные факты для выбранных УИК"""
        updated = 0
        for instance in queryset:
            instance.recalculate_all()
            updated += 1
        
        self.message_user(
            request, 
            f'Пересчитано {updated} записей UIKResultsDaily'
        )
    
    @admin.action(description='Пересчитать все факты в системе')
    def recalculate_all_daily_facts(self, request, queryset):
        """Пересчитать все расчетные факты в системе"""
        from django.core.management import call_command
        from io import StringIO
        import sys
        
        # Перенаправляем вывод команды
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            call_command('recalculate_all_daily_facts')
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        
        self.message_user(
            request, 
            f'Выполнен пересчет всех фактов: {output}'
        )
