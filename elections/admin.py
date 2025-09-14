from django.contrib import admin
from django.contrib.admin import RelatedOnlyFieldListFilter, SimpleListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.shortcuts import render
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display, action
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.sections import TableSection
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from import_export.formats.base_formats import XLSX, CSV, XLS
from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect
from datetime import date

from .models import User, UIK, Workplace, Voter, UIKResults, UIKAnalysis, UIKResultsDaily, Analytics


# Кастомные фильтры для VoterAdmin
class VotingDateFilter(SimpleListFilter):
    """Фильтр по дате голосования (12, 13, 14 сентября 2025)"""
    title = 'Дата голосования'
    parameter_name = 'voting_date'
    
    def lookups(self, request, model_admin):
        return (
            ('2025-09-12', '12 сентября 2025'),
            ('2025-09-13', '13 сентября 2025'),
            ('2025-09-14', '14 сентября 2025'),
            ('no_date', 'Без даты голосования'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'no_date':
            return queryset.filter(voting_date__isnull=True)
        elif self.value() in ['2025-09-12', '2025-09-13', '2025-09-14']:
            return queryset.filter(voting_date=self.value())
        return queryset


class PlannedDateFilter(SimpleListFilter):
    """Фильтр по плановой дате (12, 13, 14 сентября 2025)"""
    title = 'Плановая дата'
    parameter_name = 'planned_date'
    
    def lookups(self, request, model_admin):
        return (
            ('2025-09-12', '12 сентября 2025'),
            ('2025-09-13', '13 сентября 2025'),
            ('2025-09-14', '14 сентября 2025'),
            ('no_date', 'Без плановой даты'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'no_date':
            return queryset.filter(planned_date__isnull=True)
        elif self.value() in ['2025-09-12', '2025-09-13', '2025-09-14']:
            return queryset.filter(planned_date=self.value())
        return queryset


class BrigadierFilter(RelatedOnlyFieldListFilter):
    """Фильтр по бригадиру с сортировкой по алфавиту"""
    
    def field_choices(self, field, request, model_admin):
        # Получаем всех бригадиров, отсортированных по алфавиту
        brigadiers = User.objects.filter(role='brigadier').order_by('last_name', 'first_name', 'middle_name')
        return [(brigadier.id, brigadier.get_full_name()) for brigadier in brigadiers]


class AgitatorFilter(RelatedOnlyFieldListFilter):
    """Фильтр по агитатору с сортировкой по алфавиту"""
    
    def field_choices(self, field, request, model_admin):
        # Получаем всех агитаторов, отсортированных по алфавиту
        agitators = User.objects.filter(role='agitator').order_by('last_name', 'first_name', 'middle_name')
        return [(agitator.id, agitator.get_full_name()) for agitator in agitators]


# Форма для массового обновления избирателей
class BulkUpdateVotersForm(forms.Form):
    """Форма для массового обновления избирателей по ID"""
    
    voter_ids = forms.CharField(
        label='ID избирателей',
        help_text='Введите ID избирателей через запятую (например: 1,2,3,4)',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '1,2,3,4,5...'})
    )
    
    voting_date = forms.DateField(
        label='Дата голосования',
        initial=date.today,
        help_text='Дата голосования (по умолчанию сегодняшняя)'
    )
    
    voting_method = forms.ChoiceField(
        label='Способ голосования',
        choices=[
            ('at_uik', 'В УИК'),
            ('at_home', 'На дому'),
        ],
        initial='at_uik',
        required=True,
        help_text='Обязательно выберите способ голосования'
    )
    
    confirmed_by_brigadier = forms.BooleanField(
        label='Подтвердить голосование',
        required=False,
        help_text='Отметить как подтвержденное бригадиром'
    )
    
    def clean_voter_ids(self):
        """Валидация списка ID"""
        ids_text = self.cleaned_data.get('voter_ids', '')
        if not ids_text.strip():
            raise ValidationError('Необходимо указать ID избирателей')
        
        try:
            ids = [int(id_str.strip()) for id_str in ids_text.split(',') if id_str.strip()]
            if not ids:
                raise ValidationError('Не найдено корректных ID')
            
            # Проверяем существование избирателей
            existing_ids = set(Voter.objects.filter(id__in=ids).values_list('id', flat=True))
            missing_ids = set(ids) - existing_ids
            
            if missing_ids:
                raise ValidationError(f'Избиратели с ID {sorted(missing_ids)} не найдены')
            
            return ids
        except ValueError:
            raise ValidationError('ID должны быть числами, разделенными запятыми')


# Секции для Unfold


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
            'is_active_participant', 'can_be_additional', 'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login'
        )
        export_order = (
            'id', 'username', 'last_name', 'first_name', 'middle_name', 
            'phone_number', 'email', 'role', 'workplace', 
            'is_active_participant', 'can_be_additional', 'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login'
        )
        import_id_fields = ('id',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    
    def before_import_row(self, row, **kwargs):
        """Валидация перед импортом строки"""
        # Проверяем обязательные поля
        if not row.get('username'):
            raise ValidationError("Логин обязателен")
        if not row.get('last_name'):
            raise ValidationError("Фамилия обязательна")
        if not row.get('first_name'):
            raise ValidationError("Имя обязательно")
        if not row.get('middle_name'):
            raise ValidationError("Отчество обязательно")
        if not row.get('phone_number'):
            raise ValidationError("Телефон обязателен")
        
        # Валидация роли
        role = row.get('role', '').lower()
        valid_roles = ['admin', 'brigadier', 'agitator', 'operator', 'analyst']
        if role and role not in valid_roles:
            raise ValidationError(f"Роль должна быть одной из: {', '.join(valid_roles)}")
        
        # Валидация телефона - убрана, поле может содержать любой текст до 50 символов
        
        # Валидация email
        email = row.get('email', '')
        if email and '@' not in email:
            raise ValidationError("Некорректный формат email")
        
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
        
        # Обработка булевых полей
        for bool_field in ['is_active_participant', 'is_active', 'is_staff', 'is_superuser']:
            value = row.get(bool_field, '')
            if value:
                if str(value).lower() in ['true', '1', 'да', 'yes']:
                    row[bool_field] = True
                elif str(value).lower() in ['false', '0', 'нет', 'no']:
                    row[bool_field] = False
                else:
                    row[bool_field] = bool(value)
    
    def before_save_instance(self, instance, row, **kwargs):
        """Обработка перед сохранением"""
        # Устанавливаем пароль по умолчанию если не задан
        if not instance.password or instance.password == '':
            instance.set_password('password123')  # Пароль по умолчанию
        
        # Устанавливаем значения по умолчанию
        if instance.is_active is None:
            instance.is_active = True
        if instance.is_active_participant is None:
            instance.is_active_participant = True
        if instance.is_staff is None:
            instance.is_staff = False
        if instance.is_superuser is None:
            instance.is_superuser = False
        if not instance.role:
            instance.role = 'admin'
            
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
        fields = ('id', 'number', 'address', 'planned_voters_count', 'brigadier', 'agitators', 'additional_brigadiers', 'created_at', 'updated_at', 'created_by', 'updated_by')
        export_order = ('id', 'number', 'address', 'planned_voters_count', 'brigadier', 'agitators', 'additional_brigadiers', 'created_at', 'updated_at', 'created_by', 'updated_by')
        import_id_fields = ('number',)  # Уникальное поле для импорта
        skip_unchanged = True
        report_skipped = True
        
    
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
        
        # Обработка дополнительных бригадиров (через запятую)
        additional_brigadiers_value = row.get('additional_brigadiers', '')
        if additional_brigadiers_value:
            brigadier_ids = []
            # Разделяем по запятой
            brigadier_identifiers = [x.strip() for x in str(additional_brigadiers_value).split(',') if x.strip()]
            
            for identifier in brigadier_identifiers:
                # Если это число (ID), ищем по ID
                if str(identifier).isdigit():
                    try:
                        brigadier = User.objects.get(id=int(identifier), role='brigadier', can_be_additional=True)
                        brigadier_ids.append(brigadier.id)
                    except User.DoesNotExist:
                        raise ValidationError(f"Дополнительный бригадир с ID '{identifier}' не найден или не может быть дополнительным")
                else:
                    # Если это строка (логин), ищем по логину
                    try:
                        brigadier = User.objects.get(username=identifier, role='brigadier', can_be_additional=True)
                        brigadier_ids.append(brigadier.id)
                    except User.DoesNotExist:
                        raise ValidationError(f"Дополнительный бригадир с логином '{identifier}' не найден или не может быть дополнительным")
            
            row['additional_brigadiers'] = ','.join(map(str, brigadier_ids))
    
    def before_save_instance(self, instance, row, **kwargs):
        """Обработка перед сохранением"""
        # Обрабатываем агитаторов после создания/обновления УИК
        agitators_value = row.get('agitators', '')
        if agitators_value:
            agitator_ids = [int(x) for x in str(agitators_value).split(',') if x.strip()]
            instance.agitators.set(agitator_ids)
        
        # Обрабатываем дополнительных бригадиров после создания/обновления УИК
        additional_brigadiers_value = row.get('additional_brigadiers', '')
        if additional_brigadiers_value:
            brigadier_ids = [int(x) for x in str(additional_brigadiers_value).split(',') if x.strip()]
            instance.additional_brigadiers.set(brigadier_ids)
        
        # Обрабатываем created_by и updated_by
        created_by_value = row.get('created_by', '')
        if created_by_value:
            if str(created_by_value).isdigit():
                try:
                    created_by = User.objects.get(id=int(created_by_value))
                    instance.created_by = created_by
                except User.DoesNotExist:
                    pass  # Игнорируем если пользователь не найден
        
        updated_by_value = row.get('updated_by', '')
        if updated_by_value:
            if str(updated_by_value).isdigit():
                try:
                    updated_by = User.objects.get(id=int(updated_by_value))
                    instance.updated_by = updated_by
                except User.DoesNotExist:
                    pass  # Игнорируем если пользователь не найден
        
        return instance


class VoterResource(resources.ModelResource):
    """Ресурс для импорта-экспорта избирателей"""
    
    class Meta:
        model = Voter
        fields = (
            'id', 'last_name', 'first_name', 'middle_name', 'birth_date', 'registration_address', 
            'phone_number', 'workplace', 'uik', 'agitator', 'is_agitator', 'is_home_voting', 'planned_date',
            'voting_date', 'voting_method', 'confirmed_by_brigadier', 'created_at', 'updated_at', 'created_by', 'updated_by'
        )
        export_order = (
            'id', 'last_name', 'first_name', 'middle_name', 'birth_date', 'registration_address', 
            'phone_number', 'workplace', 'uik', 'agitator', 'is_agitator', 'is_home_voting', 'planned_date',
            'voting_date', 'voting_method', 'confirmed_by_brigadier', 'created_at', 'updated_at', 'created_by', 'updated_by'
        )
        import_id_fields = ('last_name', 'first_name', 'middle_name', 'birth_date')  # Уникальные поля для импорта
        skip_unchanged = True
        report_skipped = True
    
    def before_import_row(self, row, **kwargs):
        """Валидация перед импортом строки"""
        from datetime import date
        
        # Проверяем обязательные поля
        if not row.get('last_name'):
            raise ValidationError("Фамилия обязательна")
        if not row.get('first_name'):
            raise ValidationError("Имя обязательно")
        if not row.get('birth_date'):
            raise ValidationError("Дата рождения обязательна")
        if not row.get('uik'):
            raise ValidationError("УИК обязателен")
        
        # Обработка дат
        planned_date_value = row.get('planned_date', '')
        if planned_date_value:
            try:
                # Пробуем разные форматы дат
                if isinstance(planned_date_value, str):
                    # Если строка, пробуем распарсить
                    from datetime import datetime
                    try:
                        # Пробуем формат YYYY-MM-DD HH:MM:SS
                        planned_date = datetime.strptime(planned_date_value, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        try:
                            # Пробуем формат YYYY-MM-DD
                            planned_date = datetime.strptime(planned_date_value, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                # Пробуем формат DD.MM.YYYY
                                planned_date = datetime.strptime(planned_date_value, '%d.%m.%Y').date()
                            except ValueError:
                                try:
                                    # Пробуем формат DD/MM/YYYY
                                    planned_date = datetime.strptime(planned_date_value, '%d/%m/%Y').date()
                                except ValueError:
                                    raise ValidationError(f"Некорректный формат даты планирования: {planned_date_value}")
                else:
                    # Если это уже объект datetime, извлекаем дату
                    if hasattr(planned_date_value, 'date'):
                        planned_date = planned_date_value.date()
                    else:
                        planned_date = planned_date_value
                
                # Проверяем, что дата входит в разрешенные
                allowed_dates = [date(2025, 9, 12), date(2025, 9, 13), date(2025, 9, 14)]
                if planned_date not in allowed_dates:
                    raise ValidationError(f"Планируемая дата должна быть 12, 13 или 14 сентября 2025 года, получена: {planned_date}")
                
                row['planned_date'] = planned_date
            except Exception as e:
                raise ValidationError(f"Ошибка обработки даты планирования: {str(e)}")
        
        # Обработка даты голосования
        voting_date_value = row.get('voting_date', '')
        if voting_date_value:
            try:
                if isinstance(voting_date_value, str):
                    from datetime import datetime
                    try:
                        # Пробуем формат YYYY-MM-DD HH:MM:SS
                        voting_date = datetime.strptime(voting_date_value, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        try:
                            # Пробуем формат YYYY-MM-DD
                            voting_date = datetime.strptime(voting_date_value, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                # Пробуем формат DD.MM.YYYY
                                voting_date = datetime.strptime(voting_date_value, '%d.%m.%Y').date()
                            except ValueError:
                                try:
                                    # Пробуем формат DD/MM/YYYY
                                    voting_date = datetime.strptime(voting_date_value, '%d/%m/%Y').date()
                                except ValueError:
                                    raise ValidationError(f"Некорректный формат даты голосования: {voting_date_value}")
                else:
                    # Если это уже объект datetime, извлекаем дату
                    if hasattr(voting_date_value, 'date'):
                        voting_date = voting_date_value.date()
                    else:
                        voting_date = voting_date_value
                
                # Проверяем, что дата входит в разрешенные
                allowed_dates = [date(2025, 9, 12), date(2025, 9, 13), date(2025, 9, 14)]
                if voting_date not in allowed_dates:
                    raise ValidationError(f"Дата голосования должна быть 12, 13 или 14 сентября 2025 года, получена: {voting_date}")
                
                row['voting_date'] = voting_date
            except Exception as e:
                raise ValidationError(f"Ошибка обработки даты голосования: {str(e)}")
        
        # Обработка даты рождения
        birth_date_value = row.get('birth_date', '')
        if birth_date_value:
            try:
                if isinstance(birth_date_value, str):
                    from datetime import datetime
                    try:
                        # Пробуем формат YYYY-MM-DD HH:MM:SS
                        birth_date = datetime.strptime(birth_date_value, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        try:
                            # Пробуем формат YYYY-MM-DD
                            birth_date = datetime.strptime(birth_date_value, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                # Пробуем формат DD.MM.YYYY
                                birth_date = datetime.strptime(birth_date_value, '%d.%m.%Y').date()
                            except ValueError:
                                try:
                                    # Пробуем формат DD/MM/YYYY
                                    birth_date = datetime.strptime(birth_date_value, '%d/%m/%Y').date()
                                except ValueError:
                                    raise ValidationError(f"Некорректный формат даты рождения: {birth_date_value}")
                else:
                    # Если это уже объект datetime, извлекаем дату
                    if hasattr(birth_date_value, 'date'):
                        birth_date = birth_date_value.date()
                    else:
                        birth_date = birth_date_value
                
                row['birth_date'] = birth_date
            except Exception as e:
                raise ValidationError(f"Ошибка обработки даты рождения: {str(e)}")
        
        # Обработка булевых полей
        confirmed_value = row.get('confirmed_by_brigadier', '')
        if confirmed_value:
            if str(confirmed_value).lower() in ['true', '1', 'да', 'yes']:
                row['confirmed_by_brigadier'] = True
            elif str(confirmed_value).lower() in ['false', '0', 'нет', 'no']:
                row['confirmed_by_brigadier'] = False
            else:
                row['confirmed_by_brigadier'] = bool(confirmed_value)
        
        # Обработка поля is_agitator
        is_agitator_value = row.get('is_agitator', '')
        if is_agitator_value:
            if str(is_agitator_value).lower() in ['true', '1', 'да', 'yes']:
                row['is_agitator'] = True
            elif str(is_agitator_value).lower() in ['false', '0', 'нет', 'no']:
                row['is_agitator'] = False
            else:
                row['is_agitator'] = bool(is_agitator_value)
        
        # Обработка поля is_home_voting
        is_home_voting_value = row.get('is_home_voting', '')
        if is_home_voting_value:
            if str(is_home_voting_value).lower() in ['true', '1', 'да', 'yes']:
                row['is_home_voting'] = True
            elif str(is_home_voting_value).lower() in ['false', '0', 'нет', 'no']:
                row['is_home_voting'] = False
            else:
                row['is_home_voting'] = bool(is_home_voting_value)
        
        # Валидация: нельзя подтвердить голосование без даты голосования
        if row.get('confirmed_by_brigadier') and not row.get('voting_date'):
            raise ValidationError("Нельзя подтвердить голосование без указания даты голосования")
        
        # Валидация: если есть дата голосования, должен быть указан способ голосования
        if row.get('voting_date') and not row.get('voting_method'):
            raise ValidationError("При указании даты голосования необходимо указать способ голосования")
    
    def before_save_instance(self, instance, row, **kwargs):
        """Обработка перед сохранением"""
        # Устанавливаем значения по умолчанию
        if not instance.planned_date:
            from datetime import date
            instance.planned_date = date(2025, 9, 12)
        
        return instance


class VoterExcelExportResource(resources.ModelResource):
    """Отдельный ресурс ТОЛЬКО для выгрузки в Excel с русскими названиями"""
    
    # Переопределяем поля с русскими названиями
    id = resources.Field(attribute='id', column_name='ID')
    last_name = resources.Field(attribute='last_name', column_name='Фамилия')
    first_name = resources.Field(attribute='first_name', column_name='Имя')
    middle_name = resources.Field(attribute='middle_name', column_name='Отчество')
    birth_date = resources.Field(attribute='birth_date', column_name='Дата рождения')
    registration_address = resources.Field(attribute='registration_address', column_name='Адрес регистрации')
    phone_number = resources.Field(attribute='phone_number', column_name='Телефон')
    workplace_name = resources.Field(attribute='workplace__name', column_name='Место работы')
    uik_number = resources.Field(attribute='uik__number', column_name='Номер УИК')
    uik_address = resources.Field(attribute='uik__address', column_name='Адрес УИК')
    brigadier_name = resources.Field(attribute='uik__brigadier__get_short_name', column_name='Бригадир')
    agitator_name = resources.Field(attribute='agitator__get_short_name', column_name='Агитатор')
    planned_date = resources.Field(attribute='planned_date', column_name='Планируемая дата голосования')
    voting_date = resources.Field(attribute='voting_date', column_name='Дата голосования')
    voting_method_display = resources.Field(attribute='get_voting_method_display', column_name='Способ голосования')
    confirmed_by_brigadier = resources.Field(attribute='confirmed_by_brigadier', column_name='Подтверждено бригадиром')
    is_agitator = resources.Field(attribute='is_agitator', column_name='Является агитатором')
    is_home_voting = resources.Field(attribute='is_home_voting', column_name='Голосование на дому')
    created_at = resources.Field(attribute='created_at', column_name='Дата создания')
    updated_at = resources.Field(attribute='updated_at', column_name='Дата обновления')
    
    class Meta:
        model = Voter
        fields = (
            'id', 'last_name', 'first_name', 'middle_name', 'birth_date', 'registration_address', 
            'phone_number', 'workplace_name', 'uik_number', 'uik_address', 'brigadier_name', 
            'agitator_name', 'planned_date', 'voting_date', 'voting_method_display', 
            'confirmed_by_brigadier', 'is_agitator', 'is_home_voting', 'created_at', 'updated_at'
        )
        export_order = (
            'id', 'last_name', 'first_name', 'middle_name', 'birth_date', 'registration_address', 
            'phone_number', 'workplace_name', 'uik_number', 'uik_address', 'brigadier_name', 
            'agitator_name', 'planned_date', 'voting_date', 'voting_method_display', 
            'confirmed_by_brigadier', 'is_agitator', 'is_home_voting', 'created_at', 'updated_at'
        )
        skip_unchanged = True
        report_skipped = True
        # ВАЖНО: НЕ указываем import_id_fields - это ресурс только для экспорта!
    
    def dehydrate_brigadier_name(self, voter):
        """Получаем ФИО бригадира"""
        if voter.uik and voter.uik.brigadier:
            return voter.uik.brigadier.get_short_name()
        return '-'
    
    def dehydrate_agitator_name(self, voter):
        """Получаем ФИО агитатора"""
        if voter.agitator:
            return voter.agitator.get_short_name()
        return '-'
    
    def dehydrate_voting_method_display(self, voter):
        """Получаем человекочитаемое название способа голосования"""
        if voter.voting_method:
            return dict(voter._meta.get_field('voting_method').choices).get(voter.voting_method, voter.voting_method)
        return '-'
    
    def dehydrate_confirmed_by_brigadier(self, voter):
        """Преобразуем булево значение в текст"""
        return 'Да' if voter.confirmed_by_brigadier else 'Нет'
    
    def dehydrate_is_agitator(self, voter):
        """Преобразуем булево значение в текст"""
        return 'Да' if voter.is_agitator else 'Нет'
    
    def dehydrate_is_home_voting(self, voter):
        """Преобразуем булево значение в текст"""
        return 'Да' if voter.is_home_voting else 'Нет'
    
    def dehydrate_birth_date(self, voter):
        """Форматируем дату рождения"""
        if voter.birth_date:
            return voter.birth_date.strftime('%d.%m.%Y')
        return '-'
    
    def dehydrate_planned_date(self, voter):
        """Форматируем планируемую дату"""
        if voter.planned_date:
            return voter.planned_date.strftime('%d.%m.%Y')
        return '-'
    
    def dehydrate_voting_date(self, voter):
        """Форматируем дату голосования"""
        if voter.voting_date:
            return voter.voting_date.strftime('%d.%m.%Y')
        return '-'
    
    def dehydrate_created_at(self, voter):
        """Форматируем дату создания"""
        if voter.created_at:
            return voter.created_at.strftime('%d.%m.%Y %H:%M')
        return '-'
    
    def dehydrate_updated_at(self, voter):
        """Форматируем дату обновления"""
        if voter.updated_at:
            return voter.updated_at.strftime('%d.%m.%Y %H:%M')
        return '-'


@admin.register(User)
class UserAdmin(ImportExportModelAdmin, BaseUserAdmin, ModelAdmin):
    """Админка для пользователей с ролями и импортом/экспортом"""
    
    # Ресурс для импорта/экспорта
    resource_class = UserResource
    import_form_class = ImportForm
    export_form_class = ExportForm
    
    # Формы Unfold для правильного стилизования
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    list_display = ['username', 'id', 'get_full_name', 'phone_number', 'role', 'workplace', 'is_active_participant', 'is_active']
    list_filter = ['role', 'is_active_participant', 'is_active', 'workplace']
    search_fields = ['username', 'first_name', 'last_name', 'phone_number', 'email', 'assigned_uiks_as_agitator__number', 'assigned_uik_as_brigadier__number']
    ordering = ['id']
    filter_horizontal = ['assigned_agitators']
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                ('username',),
                ('last_name', 'first_name', 'middle_name', 'phone_number', 'email')
            )
        }),

        ('Роль участника', {
            'fields': ('role', 'workplace', 'is_active_participant', 'can_be_additional'),
            'description': 'Выберите роль и место работы пользователя.'
        }),
        ('Связи с агитаторами', {
            'fields': ('assigned_agitators',),
            'description': 'Назначьте агитаторов для этого бригадира (только для роли "бригадир")',
            'classes': ('collapse',)
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
            'fields': ('role', 'workplace', 'can_be_additional'),
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
            # Возвращаем форму с ошибками вместо response_add
            form = self.get_form(request, obj=None)
            return self.render_change_form(request, context={'form': form, 'errors': getattr(e, 'message_dict', {})}, change=False)
        except Exception as e:
            from django.contrib import messages
            from django.db.models.fields.related_descriptors import RelatedObjectDoesNotExist
            if isinstance(e, RelatedObjectDoesNotExist):
                messages.error(request, "Ошибка: не указан УИК. Поле 'УИК' является обязательным для создания избирателя.")
            else:
                messages.error(request, f"Ошибка при создании записи: {str(e)}")
            # Возвращаем форму с ошибками
            form = self.get_form(request, obj=None)
            return self.render_change_form(request, context={'form': form}, change=False)
    
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
    import_form_class = ImportForm
    export_form_class = ExportForm
    list_display = ['number', 'address_short', 'brigadier_display', 'agitators_display', 'additional_brigadiers_display', 'planned_voters_count', 'actual_voters_count', 'voters_difference', 'has_results']
    list_filter = ['brigadier', 'created_at']
    search_fields = ['number', 'address']
    ordering = ['number']
    readonly_fields = ['created_by', 'updated_by', 'created_at', 'updated_at']
    filter_horizontal = ['agitators', 'additional_brigadiers']
    autocomplete_fields = ['brigadier']
    
    # Поля для редактирования
    fieldsets = (
        ('Основная информация', {
            'fields': ('number', 'address', 'planned_voters_count')
        }),
        ('Персонал', {
            'fields': ('brigadier', 'agitators', 'additional_brigadiers'),
            'description': 'Назначьте бригадира, агитаторов и дополнительных бригадиров для УИК'
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
    
    def get_form(self, request, obj=None, **kwargs):
        """Получение формы с фильтрацией агитаторов"""
        form = super().get_form(request, obj, **kwargs)
        
        # Фильтруем агитаторов - убираем уже назначенных на другие УИК
        if 'agitators' in form.base_fields:
            agitators_field = form.base_fields['agitators']
            
            # Получаем всех агитаторов, которые уже назначены на другие УИК
            assigned_agitator_ids = set()
            for uik in UIK.objects.exclude(id=obj.id if obj else None):
                assigned_agitator_ids.update(uik.agitators.values_list('id', flat=True))
            
            # Фильтруем queryset
            available_agitators = User.objects.filter(
                role='agitator',
                is_active_participant=True
            ).exclude(id__in=assigned_agitator_ids)
            
            agitators_field.queryset = available_agitators
        
        return form
    
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
    
    @display(description='Факт')
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
    
    @display(description='Бригадир')
    def brigadier_display(self, obj):
        """Отображение бригадира в формате Фамилия И.О."""
        if obj.brigadier:
            return obj.brigadier.get_short_name()
        return '-'
    
    @display(description='Агитаторы')
    def agitators_display(self, obj):
        """Отображение агитаторов в формате Фамилия И.О. с переносами строк"""
        if obj.agitators.exists():
            agitators_list = []
            for agitator in obj.agitators.all():
                agitators_list.append(agitator.get_short_name())
            return format_html('<br>'.join(agitators_list))
        return '-'
    
    @display(description='Доп. бригадиры')
    def additional_brigadiers_display(self, obj):
        """Отображение дополнительных бригадиров в формате Фамилия И.О. с переносами строк"""
        if obj.additional_brigadiers.exists():
            brigadiers_list = []
            for brigadier in obj.additional_brigadiers.all():
                brigadiers_list.append(brigadier.get_short_name())
            return format_html('<br>'.join(brigadiers_list))
        return '-'
    
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
    import_form_class = ImportForm
    export_form_class = ExportForm
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
    """Админка для избирателей с разграничением прав"""
    
    resource_class = VoterResource
    import_form_class = ImportForm
    export_form_class = ExportForm
    # export_form_class = SelectableFieldsExportForm  # Альтернативный вариант с выбором полей
    
    class Media:
        css = {
            'all': ('admin/css/voter_admin.css',)
        }
        js = ('admin/js/voter_admin.js',)
    
    def get_changelist_form(self, request, **kwargs):
        """Переопределяем форму changelist для настройки виджетов полей даты"""
        form = super().get_changelist_form(request, **kwargs)
        
        if form:
            # Настраиваем виджеты для полей даты
            if 'planned_date' in form.base_fields:
                planned_date_widget = form.base_fields['planned_date'].widget
                planned_date_widget.attrs.update({
                    'style': 'width: 100px !important; max-width: 100px !important; min-width: 100px !important;',
                    'size': '10'
                })
            
            if 'voting_date' in form.base_fields:
                voting_date_widget = form.base_fields['voting_date'].widget
                voting_date_widget.attrs.update({
                    'style': 'width: 100px !important; max-width: 100px !important; min-width: 100px !important;',
                    'size': '10'
                })
        
        return form
    
    list_display = ['id', 'full_name', 'birth_date_display', 'uik', 'brigadier_display', 'agitator', 'is_agitator', 'is_home_voting', 'planned_date', 'voting_date', 'voting_method', 'confirmed_by_brigadier', 'voting_status_display']
    list_filter = ['voting_method', 'confirmed_by_brigadier', 'is_agitator', 'is_home_voting', 'uik', ('uik__brigadier', BrigadierFilter), ('agitator', AgitatorFilter), 'workplace', VotingDateFilter, PlannedDateFilter, 'created_at']
    search_fields = ['id', 'last_name', 'first_name', 'middle_name']
    list_editable = ['planned_date', 'voting_date', 'voting_method', 'confirmed_by_brigadier', 'is_agitator', 'is_home_voting']
    list_per_page = 50
    autocomplete_fields = ['agitator']
    ordering = ['id']
    # Форматы для импорта-экспорта
    formats = [XLSX, CSV]
    
    # Changelist actions (кнопки в верхней части списка)
    actions_list = ['bulk_confirm_voters', 'export_to_excel']
    
    
    @admin.display(description='Дата рождения', ordering='birth_date')
    def birth_date_display(self, obj):
        """Компактное отображение даты рождения в формате дд.мм.гггг"""
        if not obj.birth_date:
            return '-'
        return obj.birth_date.strftime('%d.%m.%Y')
        
    def changelist_view(self, request, extra_context=None):
        """Кастомизация отображения списка избирателей"""
        extra_context = extra_context or {}
        extra_context['title'] = 'Избиратели'
        extra_context['subtitle'] = 'Управление избирателями'
        
        # Обработка POST запроса для массового редактирования
        if request.method == 'POST':
            # Получаем данные из POST
            form_data = request.POST
            
            # Собираем все записи для обновления
            records_to_update = {}
            
            # Сначала собираем все данные
            for key, value in form_data.items():
                if key.startswith('form-') and '-id' in key:
                    record_id = value
                    if record_id:
                        prefix = key.replace('-id', '')
                        if record_id not in records_to_update:
                            records_to_update[record_id] = {'prefix': prefix}
                        
                        # Собираем все поля для этой записи
                        for field_name in ['planned_date', 'voting_date', 'voting_method', 'confirmed_by_brigadier']:
                            field_key = f'{prefix}-{field_name}'
                            if field_key in form_data:
                                records_to_update[record_id][field_name] = form_data[field_key]
            
            # Счетчики для уведомлений
            updated_count = 0
            error_count = 0
            
            # Теперь обновляем записи
            for record_id, data in records_to_update.items():
                try:
                    voter = Voter.objects.get(id=record_id)
                    
                    # Обновляем все поля
                    if 'planned_date' in data:
                        planned_date_str = data['planned_date']
                        if planned_date_str:
                            from datetime import datetime
                            try:
                                # Пробуем разные форматы дат
                                try:
                                    voter.planned_date = datetime.strptime(planned_date_str, '%d.%m.%Y').date()
                                except ValueError:
                                    try:
                                        voter.planned_date = datetime.strptime(planned_date_str, '%Y-%m-%d').date()
                                    except ValueError:
                                        pass
                            except Exception:
                                pass
                    
                    if 'voting_date' in data:
                        voting_date_str = data['voting_date']
                        if voting_date_str:
                            from datetime import datetime
                            try:
                                # Пробуем разные форматы дат
                                try:
                                    voter.voting_date = datetime.strptime(voting_date_str, '%d.%m.%Y').date()
                                except ValueError:
                                    try:
                                        voter.voting_date = datetime.strptime(voting_date_str, '%Y-%m-%d').date()
                                    except ValueError:
                                        voter.voting_date = None
                            except Exception:
                                voter.voting_date = None
                        else:
                            voter.voting_date = None
                    
                    if 'voting_method' in data:
                        voter.voting_method = data['voting_method']
                    
                    if 'confirmed_by_brigadier' in data:
                        voter.confirmed_by_brigadier = True
                    else:
                        voter.confirmed_by_brigadier = False
                    
                    # Сохраняем запрос для валидации
                    voter._request = request
                    
                    # Вызываем валидацию и сохраняем
                    try:
                        voter.clean()
                        voter.save()
                        updated_count += 1
                    except ValidationError as e:
                        error_count += 1
                        from django.contrib import messages
                        for field, errors in e.message_dict.items():
                            for error in errors:
                                messages.error(request, f"Запись {voter.get_full_name()}: {field}: {error}")
                    
                except Voter.DoesNotExist:
                    error_count += 1
                except Exception as e:
                    error_count += 1
                    from django.contrib import messages
                    messages.error(request, f"Ошибка при сохранении записи: {str(e)}")
            
            # Показываем итоговые уведомления
            from django.contrib import messages
            if updated_count > 0:
                messages.success(request, f"Успешно обновлено записей: {updated_count}")
            if error_count > 0:
                messages.warning(request, f"Записей с ошибками: {error_count}")
            if updated_count == 0 and error_count == 0:
                messages.info(request, "Нет изменений для сохранения")
        
        try:
            return super().changelist_view(request, extra_context)
        except ValueError as e:
            # Обрабатываем ошибку "VoterForm has no field named 'agitator'"
            if "'VoterForm' has no field named 'agitator'" in str(e):
                from django.contrib import messages
                messages.error(
                    request, 
                    "❌ Ошибка: Некоторые агитаторы не имеют назначенного УИК. "
                    "Сначала назначьте агитаторов в УИК через раздел 'УИК', а затем сохраняйте избирателей."
                )
                # Возвращаем форму с ошибками
                return self.response_post_save_change(request, None)
            else:
                raise e
        except ValidationError as e:
            # Обрабатываем ошибки валидации
            from django.contrib import messages
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"Ошибка валидации: {error}")
            return self.response_post_save_change(request, None)
    
    

    def get_fieldsets(self, request, obj=None):
        """Динамические поля в зависимости от роли"""
        base_fields = (
            ('last_name', 'first_name', 'middle_name', 'birth_date'),
            ('phone_number', 'workplace', 'registration_address'),
            ('is_agitator', 'is_home_voting')
        )
        
        if request.user.role == 'agitator':
            return (
                ('Персональные данные', {'fields': base_fields}),
                ('Планирование', {
                    'fields': ('agitator', 'planned_date'),
                    'description': 'Выберите агитатора. УИК автоматически заполнится из УИК агитатора.'
                }),
            )
        
        elif request.user.role == 'brigadier':
            return (
                ('Персональные данные', {'fields': base_fields}),
                ('Планирование', {
                    'fields': ('agitator', 'planned_date'),
                    'description': 'Выберите агитатора. УИК автоматически заполнится из УИК агитатора.'
                }),
                ('Голосование', {
                    'fields': ('voting_date', 'voting_method', 'confirmed_by_brigadier'),
                    'description': 'Вы можете подтверждать голосование'
                }),
            )
        
        else:  # admin
            return (
                ('Персональные данные', {'fields': base_fields}),
                ('Планирование', {
                    'fields': ('agitator', 'planned_date'),
                    'description': 'Выберите агитатора. УИК автоматически заполнится из УИК агитатора.'
                }),
                ('Голосование', {'fields': ('voting_date', 'voting_method', 'confirmed_by_brigadier')}),
            )
    
    def get_readonly_fields(self, request, obj=None):
        """Поля только для чтения"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        if request.user.role == 'agitator':
            readonly_fields.extend(['confirmed_by_brigadier'])
        elif request.user.role == 'brigadier':
            readonly_fields.extend(['agitator'])
        
        return readonly_fields
    
    def get_queryset(self, request):
        """Ограничиваем доступ по ролям"""
        qs = super().get_queryset(request)
        
        if request.user.role == 'brigadier':
            return qs.filter(uik__brigadier=request.user)
        elif request.user.role == 'agitator':
            return qs.filter(uik__agitators=request.user)
        
        return qs
    
    def save_model(self, request, obj, form, change):
        """Сохранение с проверкой прав и УИК агитатора"""
        # Сохраняем запрос для валидации
        obj._request = request
        
        # Проверяем, что у агитатора есть УИК
        if obj.agitator and not obj.agitator.assigned_uiks_as_agitator.exists():
            from django.contrib import messages
            messages.error(
                request, 
                f"❌ Ошибка: У агитатора '{obj.agitator.get_full_name()}' не назначен УИК. "
                f"Сначала назначьте агитатора в УИК, а затем создавайте избирателей."
            )
            return
        
        # УИК автоматически заполняется из агитатора в методе save модели
        
        # Вызываем валидацию модели
        try:
            obj.clean()
        except ValidationError as e:
            # Если есть ошибки валидации, показываем их пользователю
            from django.contrib import messages
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return
        
        super().save_model(request, obj, form, change)
    

    def get_form(self, request, obj=None, **kwargs):
        """Получение формы с дополнительными настройками"""
        form = super().get_form(request, obj, **kwargs)
        return form
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Сортировка связанных объектов по алфавиту"""
        if db_field.name == 'agitator':
            kwargs['queryset'] = User.objects.filter(role='agitator').order_by('last_name', 'first_name', 'middle_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    
    def save_related(self, request, form, formsets, change):
        """Сохранение связанных объектов"""
        super().save_related(request, form, formsets, change)
    
    def response_change(self, request, obj):
        """Обработка ответа после изменения объекта"""
        return super().response_change(request, obj)
    
    def delete_model(self, request, obj):
        """Безопасное удаление одной записи"""
        try:
            # Проверяем, есть ли связанные объекты, которые могут блокировать удаление
            from django.db import transaction
            
            with transaction.atomic():
                # Проверяем связи перед удалением
                voter_name = obj.get_full_name()
                
                # Удаляем объект
                obj.delete()
                
                from django.contrib import messages
                messages.success(request, f"Запись '{voter_name}' успешно удалена")
                
        except Exception as e:
            from django.contrib import messages
            error_msg = str(e)
            if "FOREIGN KEY constraint failed" in error_msg:
                messages.error(request, f"Нельзя удалить запись '{obj.get_full_name()}': есть связанные данные. Обратитесь к администратору.")
            else:
                messages.error(request, f"Ошибка при удалении записи '{obj.get_full_name()}': {error_msg}")
    
    def delete_queryset(self, request, queryset):
        """Безопасное удаление множества записей"""
        deleted_count = 0
        error_count = 0
        
        from django.db import transaction
        
        for obj in queryset:
            try:
                with transaction.atomic():
                    obj.delete()
                    deleted_count += 1
            except Exception as e:
                error_count += 1
                from django.contrib import messages
                error_msg = str(e)
                if "FOREIGN KEY constraint failed" in error_msg:
                    messages.error(request, f"Нельзя удалить запись '{obj.get_full_name()}': есть связанные данные")
                else:
                    messages.error(request, f"Ошибка при удалении записи '{obj.get_full_name()}': {error_msg}")
        
        # Показываем итоговые уведомления
        from django.contrib import messages
        if deleted_count > 0:
            messages.success(request, f"Успешно удалено записей: {deleted_count}")
        if error_count > 0:
            messages.warning(request, f"Записей с ошибками при удалении: {error_count}")
    
    def clean(self):
        """Валидация в зависимости от роли пользователя"""
        super().clean()
        
        # Получаем текущего пользователя из контекста
        request = getattr(self, '_request', None)
        if not request:
            return
        
        # Агитатор не может устанавливать подтверждение
        if request.user.role == 'agitator' and self.confirmed_by_brigadier:
            raise ValidationError({
                'confirmed_by_brigadier': 'Только бригадир может подтверждать голосование'
            })
        
        # Проверяем, что агитатор работает в этом УИК
        if self.agitator and self.uik:
            if not self.uik.agitators.filter(id=self.agitator.id).exists():
                raise ValidationError({
                    'agitator': f'Агитатор {self.agitator.get_full_name()} не работает в УИК {self.uik.number}'
                })
        
        # Валидация: нельзя подтвердить голосование без даты голосования
        if self.confirmed_by_brigadier and not self.voting_date:
            raise ValidationError({
                'confirmed_by_brigadier': 'Нельзя подтвердить голосование без указания даты голосования'
            })
        
        # Валидация: если есть дата голосования, должен быть указан способ голосования
        if self.voting_date and not self.voting_method:
            raise ValidationError({
                'voting_method': 'При указании даты голосования необходимо указать способ голосования'
            })
    
    @display(description='ФИО')
    def full_name(self, obj):
        """Полное имя избирателя"""
        return obj.get_full_name()
    
    @display(description='Дата рождения')
    def birth_date(self, obj):
        """Компактное отображение даты рождения"""
        if obj.birth_date:
            # Принудительно форматируем дату без локализации
            return obj.birth_date.strftime('%d.%m.%y')
        return '-'
    
    
    @display(description='УИК')
    def uik(self, obj):
        """Компактное отображение УИК"""
        return f"№{obj.uik.number}"
    
    
    @display(description='Бригадир')
    def brigadier_display(self, obj):
        """Отображение бригадира УИК"""
        if obj.uik and obj.uik.brigadier:
            return f"{obj.uik.brigadier.last_name} {obj.uik.brigadier.first_name[0]}.{obj.uik.brigadier.middle_name[0]}."
        return '-'
    
    @display(description='Агитатор')
    def agitator(self, obj):
        """Компактное отображение агитатора"""
        if obj.agitator:
            # Показываем только фамилию и инициалы
            return f"{obj.agitator.last_name} {obj.agitator.first_name[0]}.{obj.agitator.middle_name[0]}."
        return '-'
    
    
    @display(description='Подтверждено')
    def confirmed_by_brigadier(self, obj):
        """Отображение подтверждения бригадиром"""
        return 'Да' if obj.confirmed_by_brigadier else 'Нет'
    
    @display(description='Способ голосования')
    def voting_method(self, obj):
        """Отображение способа голосования"""
        if obj.voting_method:
            return dict(obj._meta.get_field('voting_method').choices).get(obj.voting_method, '')
        return '-'
    
    @display(description='Подтверждение')
    def confirmed_by_brigadier(self, obj):
        """Отображение подтверждения бригадиром"""
        return 'Да' if obj.confirmed_by_brigadier else 'Нет'
    
    @display(description='Способ голосования')
    def voting_method(self, obj):
        """Отображение способа голосования"""
        if obj.voting_method:
            return dict(obj._meta.get_field('voting_method').choices).get(obj.voting_method, '')
        return '-'
    
    @display(description='Статус голосования')
    def voting_status_display(self, obj):
        """Цветовое отображение статуса голосования с разделением на 2 строки"""
        if obj.is_voted:
            method_display = dict(obj._meta.get_field('voting_method').choices).get(obj.voting_method, '')
            return format_html(
                '<div style="color: #28a745; font-weight: 500;">✓ Проголосовал</div>'
                '<div style="color: #6c757d; font-size: 11px;">{}</div>',
                method_display
            )
        else:
            return format_html(
                '<div style="color: #007bff; font-weight: 500;">📋 Запланирован</div>'
                '<div style="color: #6c757d; font-size: 11px;">Ожидает</div>'
            )
    


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
        
        # Оптимизация запросов
        return qs.prefetch_related(
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
    
    @action(description="Подтверждение", url_path="bulk-confirm", permissions=["bulk_confirm_voters"])
    def bulk_confirm_voters(self, request):
        """Changelist action для массового подтверждения избирателей"""
        if request.method == 'POST':
            form = BulkUpdateVotersForm(request.POST)
            if form.is_valid():
                voter_ids = form.cleaned_data['voter_ids']
                voting_date = form.cleaned_data['voting_date']
                voting_method = form.cleaned_data['voting_method']
                confirmed_by_brigadier = form.cleaned_data['confirmed_by_brigadier']
                
                # Получаем избирателей для обновления
                voters = Voter.objects.filter(id__in=voter_ids)
                
                updated_count = 0
                skipped_count = 0
                error_count = 0
                errors = []
                updated_voters = []
                skipped_voters = []
                
                for voter in voters:
                    try:
                        # Проверяем, какие поля нужно обновить
                        needs_update = False
                        changes = []
                        
                        # Проверяем дату голосования
                        if not voter.voting_date and voting_date:
                            voter.voting_date = voting_date
                            needs_update = True
                            changes.append("дата голосования")
                        elif voter.voting_date:
                            skipped_voters.append(f"ID {voter.id} ({voter.get_full_name()}) - дата голосования уже заполнена")
                        
                        # Проверяем способ голосования
                        if not voter.voting_method and voting_method:
                            voter.voting_method = voting_method
                            needs_update = True
                            changes.append("способ голосования")
                        elif voter.voting_method:
                            skipped_voters.append(f"ID {voter.id} ({voter.get_full_name()}) - способ голосования уже заполнен")
                        
                        # Проверяем подтверждение бригадиром
                        if confirmed_by_brigadier and not voter.confirmed_by_brigadier:
                            voter.confirmed_by_brigadier = True
                            needs_update = True
                            changes.append("подтверждение бригадиром")
                        elif voter.confirmed_by_brigadier:
                            skipped_voters.append(f"ID {voter.id} ({voter.get_full_name()}) - уже подтверждено бригадиром")
                        
                        if needs_update:
                            # Сохраняем запрос для валидации
                            voter._request = request
                            
                            # Вызываем валидацию и сохраняем
                            voter.clean()
                            voter.save()
                            updated_count += 1
                            updated_voters.append(f"ID {voter.id} ({voter.get_full_name()}) - обновлено: {', '.join(changes)}")
                        else:
                            skipped_count += 1
                        
                    except ValidationError as e:
                        error_count += 1
                        for field, field_errors in e.message_dict.items():
                            for error in field_errors:
                                errors.append(f"ID {voter.id} ({voter.get_full_name()}): {field}: {error}")
                    except Exception as e:
                        error_count += 1
                        errors.append(f"ID {voter.id} ({voter.get_full_name()}): {str(e)}")
                
                # Подготавливаем данные для модального окна
                result_data = {
                    'updated': updated_count,
                    'skipped': skipped_count,
                    'errors': error_count,
                    'updated_list': updated_voters[:10],  # Показываем первые 10
                    'skipped_list': skipped_voters[:10],  # Показываем первые 10
                    'error_list': errors[:10],  # Показываем первые 10
                    'show_modal': True
                }
                
                # Всегда показываем форму с результатами в модальном окне
                context = {
                    'title': 'Массовое подтверждение избирателей',
                    'form': BulkUpdateVotersForm(),  # Новая форма
                    'opts': self.model._meta,
                    'result_data': result_data,
                }
                return render(request, 'admin/bulk_confirm_voters.html', context)
        else:
            form = BulkUpdateVotersForm()
        
        context = {
            'title': 'Массовое подтверждение избирателей',
            'form': form,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/bulk_confirm_voters.html', context)
    
    def get_search_results(self, request, queryset, search_term):
        """Кастомный поиск по ID и ФИО с нечувствительностью к регистру"""
        if search_term:
            search_term = search_term.strip()
            
            # Поиск по ID (точный)
            if search_term.isdigit():
                queryset = queryset.filter(id=search_term)
            else:
                # Очищаем от лишних символов и разбиваем на слова
                cleaned_term = search_term.replace('.', '').replace(',', '').replace('  ', ' ').strip()
                terms = [term.strip() for term in cleaned_term.split() if term.strip()]
                
                if terms:
                    # Создаем Q объект для поиска по каждому слову
                    q_objects = Q()
                    
                    for term in terms:
                        # Поиск по отдельным полям ФИО с разными вариантами регистра
                        # Создаем варианты регистра для кириллицы
                        term_variants = [term, term.capitalize(), term.upper()]
                        
                        field_search = Q()
                        for variant in term_variants:
                            field_search |= (
                                Q(last_name__icontains=variant) |
                                Q(first_name__icontains=variant) |
                                Q(middle_name__icontains=variant)
                            )
                        
                        # Добавляем как AND условие (все слова должны найтись)
                        q_objects &= field_search
                    
                    queryset = queryset.filter(q_objects)
        
        return queryset, False
    
    def has_bulk_confirm_voters_permission(self, request):
        """Проверка прав на массовое подтверждение"""
        # Только админы, операторы и бригадиры могут подтверждать
        return (request.user.is_superuser or 
                request.user.role in ['admin', 'operator', 'brigadier'])
    
    @action(description="Выгрузка в Excel", url_path="export-to-excel", permissions=["export_to_excel"])
    def export_to_excel(self, request):
        """Выгрузка избирателей в Excel с русскими названиями и человекочитаемыми данными"""
        from django.http import HttpResponse
        from import_export.formats.base_formats import XLSX
        from datetime import datetime
        
        # Получаем queryset с учетом фильтров
        queryset = self.get_queryset(request)
        
        # Применяем фильтры из request
        if hasattr(request, 'GET') and request.GET:
            # Применяем фильтры из URL параметров
            for key, value in request.GET.items():
                if key.startswith('uik__') or key.startswith('agitator__') or key.startswith('workplace__'):
                    if value:
                        queryset = queryset.filter(**{key: value})
        
        # Создаем ресурс для экспорта
        resource = VoterExcelExportResource()
        
        # Экспортируем данные
        dataset = resource.export(queryset)
        
        # Создаем Excel файл
        xlsx_format = XLSX()
        response = HttpResponse(
            xlsx_format.export_data(dataset),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Генерируем имя файла с текущей датой
        current_date = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'izbirateli_{current_date}.xlsx'
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    def has_export_to_excel_permission(self, request):
        """Проверка прав на выгрузку в Excel"""
        # Все пользователи с правами на просмотр могут экспортировать
        return request.user.has_perm('elections.view_voter')


@admin.register(UIKResults)
class UIKResultsAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для результатов по УИК с редактированием в списке"""
    
    import_form_class = ImportForm
    export_form_class = ExportForm
    
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
    
    import_form_class = ImportForm
    export_form_class = ExportForm
    
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






# Хелпер для проверки группы
OPERATORS_GROUP = 'Операторы избирателей'
def is_operators_user(user):
    return user.groups.filter(name=OPERATORS_GROUP).exists()


@admin.register(UIKResultsDaily)
class UIKResultsDailyAdmin(ImportExportModelAdmin, ModelAdmin):
    """Админка для результатов по дням УИК с редактированием в списке"""
    
    import_form_class = ImportForm
    export_form_class = ExportForm
    
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
        """Автоматически заполняем поля created_by и updated_by"""
        if not change:  # Создание новой записи
            obj.created_by = request.user
        obj.updated_by = request.user
        
        # Сохраняем объект
        super().save_model(request, obj, form, change)
    
    # Действия для массовых операций
    actions = ['recalculate_daily_facts', 'recalculate_all_daily_facts', 'sync_manual_with_calculated']
    
    def get_changelist_form(self, request, **kwargs):
        """Кастомная форма для changelist"""
        form = super().get_changelist_form(request, **kwargs)
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
    
    @admin.action(description='Синхронизировать вписанные значения с расчетными')
    def sync_manual_with_calculated(self, request, queryset):
        """Синхронизировать вписанные значения с расчетными для выбранных УИК"""
        updated = 0
        for instance in queryset:
            # Принудительно обновляем вписанные значения на расчетные для незаблокированных дней
            if not instance.fact_12_sep_locked:
                instance.fact_12_sep = instance.fact_12_sep_calculated
                instance.fact_12_sep_source = 'calculated'
            
            if not instance.fact_13_sep_locked:
                instance.fact_13_sep = instance.fact_13_sep_calculated
                instance.fact_13_sep_source = 'calculated'
            
            if not instance.fact_14_sep_locked:
                instance.fact_14_sep = instance.fact_14_sep_calculated
                instance.fact_14_sep_source = 'calculated'
            
            instance.save(update_fields=[
                'fact_12_sep', 'fact_13_sep', 'fact_14_sep',
                'fact_12_sep_source', 'fact_13_sep_source', 'fact_14_sep_source'
            ])
            updated += 1
        
        self.message_user(
            request, 
            f'Синхронизировано {updated} записей UIKResultsDaily. Вписанные значения обновлены на расчетные для незаблокированных дней.'
        )
