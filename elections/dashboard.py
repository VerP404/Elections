
from django.db.models import Count, Q, Sum
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminDecimalFieldWidget
from .models import UIK, Voter, User, UIKResults, UIKAnalysis, UIKResultsDaily, Workplace
from datetime import date
from decimal import Decimal


def main_dashboard_callback(request, context):
    """Callback для главного дашборда админки с общей статистикой"""
    # Получаем данные анализа по УИК
    analysis_data = UIKAnalysis.objects.select_related('uik').all()
    
    # Получаем данные по дням из UIKResultsDaily
    daily_data = UIKResultsDaily.objects.select_related('uik').all()
    
    # Статистика анализа
    analysis_stats = {
        'total_uiks': analysis_data.count(),
        'completed_uiks': sum(1 for analysis in analysis_data if analysis.plan_execution_percentage >= 100),
        'total_planned_voters': sum(analysis.total_plan for analysis in analysis_data),
        'total_confirmed_voters': sum(analysis.total_fact for analysis in analysis_data),
        'voters_percentage': 0,
    }
    
    if analysis_stats['total_planned_voters'] > 0:
        analysis_stats['voters_percentage'] = round(
            (analysis_stats['total_confirmed_voters'] / analysis_stats['total_planned_voters'] * 100), 1
        )
    
    # Статистика результатов по дням
    results_stats = {
        'total_plan': sum(item.total_plan for item in daily_data),
        'total_fact': sum(item.total_fact for item in daily_data),
        'plan_execution_percent': 0,
        'total_plan_12_sep': sum(item.plan_12_sep for item in daily_data),
        'total_12_sep': sum(item.get_effective_fact_12_sep() for item in daily_data),
        'plan_12_percent': 0,
        'total_plan_13_sep': sum(item.plan_13_sep for item in daily_data),
        'total_13_sep': sum(item.get_effective_fact_13_sep() for item in daily_data),
        'plan_13_percent': 0,
        'total_plan_14_sep': sum(item.plan_14_sep for item in daily_data),
        'total_14_sep': sum(item.get_effective_fact_14_sep() for item in daily_data),
        'plan_14_percent': 0,
    }
    
    # Вычисляем проценты для результатов
    if results_stats['total_plan'] > 0:
        results_stats['plan_execution_percent'] = round(
            (results_stats['total_fact'] / results_stats['total_plan'] * 100), 1
        )
    
    if results_stats['total_plan_12_sep'] > 0:
        results_stats['plan_12_percent'] = round(
            (results_stats['total_12_sep'] / results_stats['total_plan_12_sep'] * 100), 1
        )
    
    if results_stats['total_plan_13_sep'] > 0:
        results_stats['plan_13_percent'] = round(
            (results_stats['total_13_sep'] / results_stats['total_plan_13_sep'] * 100), 1
        )
    
    if results_stats['total_plan_14_sep'] > 0:
        results_stats['plan_14_percent'] = round(
            (results_stats['total_14_sep'] / results_stats['total_plan_14_sep'] * 100), 1
        )
    
    # Время последнего обновления
    last_update_time = None
    if analysis_data.exists():
        last_analysis = analysis_data.order_by('-updated_at').first()
        last_update_time = last_analysis.updated_at
    
    # Передаем данные в контекст для кастомного шаблона
    context.update({
        # Статистика анализа
        'analysis_total_uiks': analysis_stats['total_uiks'],
        'analysis_completed_uiks': analysis_stats['completed_uiks'],
        'analysis_total_planned_voters': analysis_stats['total_planned_voters'],
        'analysis_total_confirmed_voters': analysis_stats['total_confirmed_voters'],
        'analysis_voters_percentage': analysis_stats['voters_percentage'],
        
        # Статистика результатов
        'results_total_plan': results_stats['total_plan'],
        'results_total_fact': results_stats['total_fact'],
        'results_plan_execution_percent': results_stats['plan_execution_percent'],
        'results_total_plan_12_sep': results_stats['total_plan_12_sep'],
        'results_total_12_sep': results_stats['total_12_sep'],
        'results_plan_12_percent': results_stats['plan_12_percent'],
        'results_total_plan_13_sep': results_stats['total_plan_13_sep'],
        'results_total_13_sep': results_stats['total_13_sep'],
        'results_plan_13_percent': results_stats['plan_13_percent'],
        'results_total_plan_14_sep': results_stats['total_plan_14_sep'],
        'results_total_14_sep': results_stats['total_14_sep'],
        'results_plan_14_percent': results_stats['plan_14_percent'],
        
        'last_update_time': last_update_time,
    })
    
    return context


def analysis_dashboard_callback(request, context):
    """Callback для дашборда анализа по УИК"""
    # Получаем данные анализа по УИК
    analysis_data = UIKAnalysis.objects.select_related('uik').all()
    
    if not analysis_data.exists():
        context.update({
            'total_uiks': 0,
            'completed_uiks': 0,
            'total_planned_voters': 0,
            'total_confirmed_voters': 0,
            'voters_percentage': 0,
            'uik_table_data': [],
            'last_update_time': None,
        })
        return context
    
    # Общая статистика
    total_uiks = analysis_data.count()
    # Подсчитываем УИК с выполнением плана >= 100% в Python, так как это свойство модели
    completed_uiks = sum(1 for analysis in analysis_data if analysis.plan_execution_percentage >= 100)
    
    # Статистика по избирателям
    total_planned_voters = sum(analysis.total_plan for analysis in analysis_data)
    total_confirmed_voters = sum(analysis.total_fact for analysis in analysis_data)
    voters_percentage = round((total_confirmed_voters / total_planned_voters * 100), 1) if total_planned_voters > 0 else 0
    
    # Данные для таблицы
    uik_table_data = []
    for analysis in analysis_data:
        execution_percent = analysis.plan_execution_percentage
        
        # Определяем цвет строки на основе выполнения плана
        if analysis.total_plan == 0:
            row_color = 'yellow'  # Желтый для плана = 0
        elif execution_percent >= 100:
            row_color = 'success'  # Зеленый
        elif execution_percent >= 80:
            row_color = 'warning'  # Оранжевый
        elif execution_percent >= 60:
            row_color = 'danger-light'  # Светло-красный
        else:
            row_color = 'danger'  # Красный
        
        uik_table_data.append({
            'uik_number': analysis.uik.number,
            'home_plan': analysis.home_plan,
            'home_fact': analysis.home_fact,
            'site_plan': analysis.site_plan,
            'site_fact': analysis.site_fact,
            'total_plan': analysis.total_plan,
            'total_fact': analysis.total_fact,
            'execution_percent': execution_percent,
            'row_color': row_color,
            'home_execution_percent': analysis.home_execution_percentage,
            'site_execution_percent': analysis.site_execution_percentage,
        })
    
    # Сортируем по номеру УИК
    uik_table_data.sort(key=lambda x: x['uik_number'])
    
    # Получаем время последнего обновления данных
    last_update_time = analysis_data.order_by('-updated_at').first().updated_at if analysis_data.exists() else None
    
    context.update({
        'total_uiks': total_uiks,
        'completed_uiks': completed_uiks,
        'total_planned_voters': total_planned_voters,
        'total_confirmed_voters': total_confirmed_voters,
        'voters_percentage': voters_percentage,
        'uik_table_data': uik_table_data,
        'last_update_time': last_update_time,
    })
    
    return context


def results_table_dashboard_callback(request, context):
    """Callback: табличный дашборд с расчетом фактов по реальным данным (Voter).

    Новая структура: УИК -> Основной бригадир -> Дополнительные бригадиры -> Агитаторы с указанием руководителя
    """
    from datetime import date
    
    # Даты голосования (фиксированные требования домена)
    allowed_dates = [
        date(2025, 9, 12),
        date(2025, 9, 13),
        date(2025, 9, 14),
    ]

    # Загружаем справочники единожды
    uiks = (
        UIK.objects
        .select_related('brigadier')
        .prefetch_related('agitators', 'additional_brigadiers')
        .all()
        .order_by('number')
    )
    daily_map = {d.uik_id: d for d in UIKResultsDaily.objects.select_related('uik').all()}

    rows = []

    # Итоговые счетчики
    total_plan_all = 0
    total_fact_all = 0
    total_plan_12 = total_plan_13 = total_plan_14 = 0
    total_fact_12 = total_fact_13 = total_fact_14 = 0

    for i, uik in enumerate(uiks):
        daily = daily_map.get(uik.id)

        # План берем из UIKResultsDaily (если нет — нули)
        plan_12 = daily.plan_12_sep if daily else 0
        plan_13 = daily.plan_13_sep if daily else 0
        plan_14 = daily.plan_14_sep if daily else 0
        plan_total = plan_12 + plan_13 + plan_14

        # Факт считаем только по реальным данным (избиратели с подтверждением и датой)
        fact_query_12 = Voter.objects.filter(uik=uik, confirmed_by_brigadier=True, voting_date=allowed_dates[0])
        fact_query_13 = Voter.objects.filter(uik=uik, confirmed_by_brigadier=True, voting_date=allowed_dates[1])
        fact_query_14 = Voter.objects.filter(uik=uik, confirmed_by_brigadier=True, voting_date=allowed_dates[2])
        
        
        fact_12 = fact_query_12.count()
        fact_13 = fact_query_13.count()
        fact_14 = fact_query_14.count()
        fact_total = fact_12 + fact_13 + fact_14

        # Проценты
        total_percent = round((fact_total / plan_total * 100), 1) if plan_total > 0 else 0
        p12 = round((fact_12 / plan_12 * 100), 1) if plan_12 > 0 else 0
        p13 = round((fact_13 / plan_13 * 100), 1) if plan_13 > 0 else 0
        p14 = round((fact_14 / plan_14 * 100), 1) if plan_14 > 0 else 0

        # Бригадиры
        main_brigadier_name = uik.brigadier.get_short_name() if uik.brigadier else '-'
        additional_brigadiers = list(uik.additional_brigadiers.all())
        
        # Собираем всех бригадиров (основной + дополнительные)
        all_brigadiers = []
        if uik.brigadier:
            all_brigadiers.append(uik.brigadier)
        all_brigadiers.extend(additional_brigadiers)

        # Логика раскрашивания
        if plan_total == 0:
            row_color = 'yellow'  # Желтая строка если план = 0
        elif total_percent >= 100:
            row_color = 'success'
        elif total_percent >= 80:
            row_color = 'warning'
        else:
            row_color = 'danger-light'

        # Строка «Итого по УИК» (сначала)
        rows.append({
            'row_type': 'total',
            'uik_number': uik.number,
            'brigadier': main_brigadier_name,
            'agitators': 'Итого по УИК',
            'managing_brigadier': '',
            'plan_total': plan_total,
            'fact_total': fact_total,
            'plan_execution_percent': total_percent,
            'plan_12_sep': plan_12,
            'fact_12_sep': fact_12,
            'plan_12_percent': p12,
            'plan_13_sep': plan_13,
            'fact_13_sep': fact_13,
            'plan_13_percent': p13,
            'plan_14_sep': plan_14,
            'fact_14_sep': fact_14,
            'plan_14_percent': p14,
            'row_color': row_color,
        })

        # Строки по каждому агитатору с указанием руководителя
        for ag in uik.agitators.all():
            # Ищем, кто управляет этим агитатором среди ВСЕХ бригадиров в системе
            managing_brigadier = ag.assigned_brigadiers.first()  # Берем первого руководителя
            
            managing_brigadier_name = managing_brigadier.get_short_name() if managing_brigadier else '-'
            
            # Считаем факты по агитатору
            a_fact_12 = Voter.objects.filter(uik=uik, agitator=ag, confirmed_by_brigadier=True, voting_date=allowed_dates[0]).count()
            a_fact_13 = Voter.objects.filter(uik=uik, agitator=ag, confirmed_by_brigadier=True, voting_date=allowed_dates[1]).count()
            a_fact_14 = Voter.objects.filter(uik=uik, agitator=ag, confirmed_by_brigadier=True, voting_date=allowed_dates[2]).count()
            a_fact_total = a_fact_12 + a_fact_13 + a_fact_14

            rows.append({
                'row_type': 'agitator',
                'uik_number': uik.number,
                'brigadier': main_brigadier_name,
                'agitators': ag.get_short_name(),
                'managing_brigadier': managing_brigadier_name,
                'plan_total': '',
                'fact_total': a_fact_total,
                'plan_execution_percent': '',
                'plan_12_sep': '',
                'fact_12_sep': a_fact_12,
                'plan_12_percent': '',
                'plan_13_sep': '',
                'fact_13_sep': a_fact_13,
                'plan_13_percent': '',
                'plan_14_sep': '',
                'fact_14_sep': a_fact_14,
                'plan_14_percent': '',
                'row_color': '',
            })

        # Добавляем разделитель между УИК (кроме последнего)
        if i < len(uiks) - 1:
            rows.append({
                'row_type': 'separator',
                'uik_number': '',
                'brigadier': '',
                'agitators': '',
                'managing_brigadier': '',
                'plan_total': '',
                'fact_total': '',
                'plan_execution_percent': '',
                'plan_12_sep': '',
                'fact_12_sep': '',
                'plan_12_percent': '',
                'plan_13_sep': '',
                'fact_13_sep': '',
                'plan_13_percent': '',
                'plan_14_sep': '',
                'fact_14_sep': '',
                'plan_14_percent': '',
                'row_color': '',
            })

        # Итоги
        total_plan_all += plan_total
        total_fact_all += fact_total
        total_plan_12 += plan_12
        total_plan_13 += plan_13
        total_plan_14 += plan_14
        total_fact_12 += fact_12
        total_fact_13 += fact_13
        total_fact_14 += fact_14

    total_percent_all = round((total_fact_all / total_plan_all * 100), 1) if total_plan_all > 0 else 0
    total_p12 = round((total_fact_12 / total_plan_12 * 100), 1) if total_plan_12 > 0 else 0
    total_p13 = round((total_fact_13 / total_plan_13 * 100), 1) if total_plan_13 > 0 else 0
    total_p14 = round((total_fact_14 / total_plan_14 * 100), 1) if total_plan_14 > 0 else 0

    context.update({
        'uik_table_rows': rows,
        'total_plan': total_plan_all,
        'total_fact': total_fact_all,
        'plan_execution_percent': total_percent_all,
        'total_plan_12_sep': total_plan_12,
        'total_plan_13_sep': total_plan_13,
        'total_plan_14_sep': total_plan_14,
        'total_12_sep': total_fact_12,
        'total_13_sep': total_fact_13,
        'total_14_sep': total_fact_14,
        'plan_12_percent': total_p12,
        'plan_13_percent': total_p13,
        'plan_14_percent': total_p14,
    })

    return context


def results_dashboard_callback(request, context):
    """Callback для дашборда результатов голосования"""
    # Получаем фильтры из localStorage (передаются через JavaScript)
    filters = request.GET.get('filters', '{}')
    import json
    try:
        filters_data = json.loads(filters)
    except:
        filters_data = {}
    
    # Получаем данные по дням из UIKResultsDaily
    daily_data = UIKResultsDaily.objects.select_related('uik').all()
    
    if not daily_data.exists():
        context.update({
            'total_plan': 0,
            'total_fact': 0,
            'plan_execution_percent': 0,
            'total_at_uik': 0,
            'total_at_home': 0,
            'total_plan_12_sep': 0,
            'total_12_sep': 0,
            'total_12_sep_uik': 0,
            'total_12_sep_home': 0,
            'plan_12_percent': 0,
            'total_plan_13_sep': 0,
            'total_13_sep': 0,
            'total_13_sep_uik': 0,
            'total_13_sep_home': 0,
            'plan_13_percent': 0,
            'total_plan_14_sep': 0,
            'total_14_sep': 0,
            'total_14_sep_uik': 0,
            'total_14_sep_home': 0,
            'plan_14_percent': 0,
            'uik_table_data': [],
            'last_update_time': None,
        })
        return context
    
    # Применяем фильтры к избирателям
    from datetime import date
    voter_filters = Q()
    
    # Фильтруем агитаторов по группам
    include_dmitriev = filters_data.get('includeDmitriev', True)
    include_gutorova = filters_data.get('includeGutorova', True)
    include_others = filters_data.get('includeOthers', True)
    
    # Если не все группы включены, применяем фильтрацию
    if not (include_dmitriev and include_gutorova and include_others):
        group_filters = Q()
        
        if include_dmitriev:
            # Список фамилий для Дмитриева
            dmitriev_surnames = [
                'Дмитриев', 'Беруашвили', 'Горюнова', 'Гуличева', 
                'Косинова', 'Масленникова', 'Пахомова', 'Ситникова', 'Солодовникова'
            ]
            dmitriev_q = Q()
            for surname in dmitriev_surnames:
                dmitriev_q |= Q(agitator__last_name__icontains=surname)
            group_filters |= dmitriev_q
            
        if include_gutorova:
            group_filters |= Q(agitator__last_name__icontains='Гуторова')
            
        if include_others:
            # Прочие - те, кто не относится к Дмитриеву и Гуторовой
            dmitriev_surnames = [
                'Дмитриев', 'Беруашвили', 'Горюнова', 'Гуличева', 
                'Косинова', 'Масленникова', 'Пахомова', 'Ситникова', 'Солодовникова'
            ]
            others_q = Q()
            for surname in dmitriev_surnames:
                others_q &= ~Q(agitator__last_name__icontains=surname)
            others_q &= ~Q(agitator__last_name__icontains='Гуторова')
            group_filters |= others_q
        
        voter_filters &= group_filters
    
    # Фильтр по группам мест работы (включаем только выбранные группы)
    workplace_groups = filters_data.get('workplaceGroups', [])
    if workplace_groups:
        # Получаем все возможные группы
        all_groups = [choice[0] for choice in Workplace.GROUP_CHOICES]
        # Применяем фильтр только если не все группы выбраны
        if len(workplace_groups) < len(all_groups):
            # Создаем условие для включения выбранных групп
            group_conditions = Q()
            
            # Добавляем выбранные группы
            for group in workplace_groups:
                if group == 'other':
                    # Для "Прочие" включаем избирателей с пустым workplace
                    group_conditions |= Q(workplace__isnull=True)
                else:
                    # Для остальных групп включаем избирателей с соответствующей группой
                    group_conditions |= Q(workplace__group=group)
            
            # Применяем условие включения
            voter_filters &= group_conditions
    
    # Общая статистика с учетом фильтров
    total_plan = sum(item.total_plan for item in daily_data)
    
    # Определяем, есть ли активные фильтры
    all_groups = [choice[0] for choice in Workplace.GROUP_CHOICES]
    # Фильтр по группам активен только если не все группы выбраны
    has_workplace_filter = workplace_groups and len(workplace_groups) < len(all_groups)
    
    has_active_filters = (not include_dmitriev or not include_gutorova or not include_others or 
                         has_workplace_filter)
    
    if has_active_filters:
        # Есть фильтры - пересчитываем факты с учетом фильтров
        filtered_voters = Voter.objects.filter(
            uik__in=[item.uik for item in daily_data],
            confirmed_by_brigadier=True,
            voting_date__isnull=False
        ).filter(voter_filters)
        
        # Считаем факты по дням с фильтрами
        total_fact_12_filtered = filtered_voters.filter(voting_date=date(2025, 9, 12)).count()
        total_fact_13_filtered = filtered_voters.filter(voting_date=date(2025, 9, 13)).count()
        total_fact_14_filtered = filtered_voters.filter(voting_date=date(2025, 9, 14)).count()
        total_fact = total_fact_12_filtered + total_fact_13_filtered + total_fact_14_filtered
    else:
        # Нет фильтров - используем существующую логику (учитывает блокировки)
        total_fact = sum(item.get_effective_fact_12_sep() + item.get_effective_fact_13_sep() + item.get_effective_fact_14_sep() for item in daily_data)
    
    plan_execution_percent = round((total_fact / total_plan * 100), 1) if total_plan > 0 else 0
    
    # Подсчет голосов по способам из новой модели Voter с фильтрами
    
    # Общий подсчет голосов В УИК (подтвержденных) с фильтрами
    uik_voters_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        voting_method='at_uik',
        confirmed_by_brigadier=True,
        voting_date__isnull=False
    )
    if has_active_filters:
        uik_voters_query = uik_voters_query.filter(voter_filters)
    total_at_uik = uik_voters_query.count()
    
    # На дому = общий факт - В УИК
    total_at_home = total_fact - total_at_uik
    
    # Статистика по дням с использованием расчетных значений и фильтров
    total_plan_12_sep = sum(item.plan_12_sep for item in daily_data)
    total_plan_13_sep = sum(item.plan_13_sep for item in daily_data)
    total_plan_14_sep = sum(item.plan_14_sep for item in daily_data)
    
    # Используем правильную логику по дням
    if has_active_filters:
        # Применяем фильтры к расчетным значениям
        total_12_sep = filtered_voters.filter(voting_date=date(2025, 9, 12)).count()
        total_13_sep = filtered_voters.filter(voting_date=date(2025, 9, 13)).count()
        total_14_sep = filtered_voters.filter(voting_date=date(2025, 9, 14)).count()
    else:
        # Нет фильтров - используем существующую логику (учитывает блокировки)
        total_12_sep = sum(item.get_effective_fact_12_sep() for item in daily_data)
        total_13_sep = sum(item.get_effective_fact_13_sep() for item in daily_data)
        total_14_sep = sum(item.get_effective_fact_14_sep() for item in daily_data)
    
    plan_12_percent = round((total_12_sep / total_plan_12_sep * 100), 1) if total_plan_12_sep > 0 else 0
    plan_13_percent = round((total_13_sep / total_plan_13_sep * 100), 1) if total_plan_13_sep > 0 else 0
    plan_14_percent = round((total_14_sep / total_plan_14_sep * 100), 1) if total_plan_14_sep > 0 else 0
    
    # Подсчет УИК/Дом для каждого дня с фильтрами
    uik_12_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        voting_method='at_uik',
        confirmed_by_brigadier=True,
        voting_date=date(2025, 9, 12)
    )
    if has_active_filters:
        uik_12_query = uik_12_query.filter(voter_filters)
    total_12_sep_uik = uik_12_query.count()
    total_12_sep_home = total_12_sep - total_12_sep_uik
    
    uik_13_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        voting_method='at_uik',
        confirmed_by_brigadier=True,
        voting_date=date(2025, 9, 13)
    )
    if has_active_filters:
        uik_13_query = uik_13_query.filter(voter_filters)
    total_13_sep_uik = uik_13_query.count()
    total_13_sep_home = total_13_sep - total_13_sep_uik
    
    uik_14_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        voting_method='at_uik',
        confirmed_by_brigadier=True,
        voting_date=date(2025, 9, 14)
    )
    if has_active_filters:
        uik_14_query = uik_14_query.filter(voter_filters)
    total_14_sep_uik = uik_14_query.count()
    total_14_sep_home = total_14_sep - total_14_sep_uik
    
    # Данные для таблицы с учетом фильтров
    uik_table_data = []
    for item in daily_data:
        # Используем правильную логику для фактов
        if has_active_filters:
            # Применяем фильтры к избирателям этого УИК
            uik_filtered_voters = Voter.objects.filter(
                uik=item.uik,
                confirmed_by_brigadier=True,
                voting_date__isnull=False
            ).filter(voter_filters)
            
            fact_12_sep = uik_filtered_voters.filter(voting_date=date(2025, 9, 12)).count()
            fact_13_sep = uik_filtered_voters.filter(voting_date=date(2025, 9, 13)).count()
            fact_14_sep = uik_filtered_voters.filter(voting_date=date(2025, 9, 14)).count()
            fact_total = fact_12_sep + fact_13_sep + fact_14_sep
        else:
            # Нет фильтров - используем существующую логику (учитывает блокировки)
            fact_12_sep = item.get_effective_fact_12_sep()
            fact_13_sep = item.get_effective_fact_13_sep()
            fact_14_sep = item.get_effective_fact_14_sep()
            fact_total = fact_12_sep + fact_13_sep + fact_14_sep
        
        # Процент выполнения плана
        execution_percent = round((fact_total / item.total_plan * 100), 1) if item.total_plan > 0 else 0
        
        # Определяем цвет строки на основе выполнения плана
        if item.total_plan == 0:
            row_color = 'yellow'  # Желтый для плана = 0
        elif execution_percent >= 100:
            row_color = 'success'  # Зеленый
        elif execution_percent >= 80:
            row_color = 'warning'  # Оранжевый
        elif execution_percent >= 60:
            row_color = 'danger-light'  # Светло-красный
        else:
            row_color = 'danger'  # Красный
        
        # Проценты по дням для таблицы
        uik_plan_12_percent = round((fact_12_sep / item.plan_12_sep * 100), 1) if item.plan_12_sep > 0 else 0
        uik_plan_13_percent = round((fact_13_sep / item.plan_13_sep * 100), 1) if item.plan_13_sep > 0 else 0
        uik_plan_14_percent = round((fact_14_sep / item.plan_14_sep * 100), 1) if item.plan_14_sep > 0 else 0
        
        # Информация о бригадире и агитаторах для tooltip
        if item.uik.brigadier:
            brigadier_phone = f" - {item.uik.brigadier.phone_number}" if item.uik.brigadier.phone_number else ""
            brigadier_info = f"{item.uik.brigadier.get_short_name()}{brigadier_phone}"
        else:
            brigadier_info = 'Не назначен'
        
        agitators_info = []
        for agitator in item.uik.agitators.all():
            agitator_phone = f" - {agitator.phone_number}" if agitator.phone_number else ""
            agitators_info.append(f"{agitator.get_short_name()}{agitator_phone}")
        agitators_text = ', '.join(agitators_info) if agitators_info else 'Не назначены'
        
        uik_table_data.append({
            'uik_number': item.uik.number,
            'plan_total': item.total_plan,
            'fact_total': fact_total,
            'plan_execution_percent': execution_percent,
            'row_color': row_color,
            'plan_12_sep': item.plan_12_sep,
            'fact_12_sep': fact_12_sep,
            'plan_12_percent': uik_plan_12_percent,
            'plan_13_sep': item.plan_13_sep,
            'fact_13_sep': fact_13_sep,
            'plan_13_percent': uik_plan_13_percent,
            'plan_14_sep': item.plan_14_sep,
            'fact_14_sep': fact_14_sep,
            'plan_14_percent': uik_plan_14_percent,
            'brigadier': brigadier_info,
            'agitators': agitators_text,
            'agitators_list': agitators_info,  # Список для отдельного отображения
        })
    
    # Сортируем по номеру УИК
    uik_table_data.sort(key=lambda x: x['uik_number'])
    
    # Получаем время последнего обновления данных
    last_update_time = daily_data.order_by('-updated_at').first().updated_at if daily_data.exists() else None
    
    # Данные для диаграмм
    # 1. Статус голосования (на основе UIKResultsDaily: Общий план и Общий факт)
    voting_status_data = {
        'labels': ['Проголосовали', 'Осталось по плану'],
        'data': [total_fact, total_plan - total_fact],
        'colors': ['#10b981', '#f59e0b']
    }
    
    # 2. Голосование по всем группам (исключая 'other') + агитаторы с фильтрами
    workplace_groups = [choice[0] for choice in Workplace.GROUP_CHOICES if choice[0] != 'other']
    group_data = []
    group_voted_data = []
    group_labels = []
    
    for group in workplace_groups:
        group_name = dict(Workplace.GROUP_CHOICES).get(group, group)
        group_labels.append(group_name)
        
        # Общее количество в группе с фильтрами
        group_voters_query = Voter.objects.filter(
            uik__in=[item.uik for item in daily_data],
            workplace__group=group
        )
        if has_active_filters:
            group_voters_query = group_voters_query.filter(voter_filters)
        total_in_group = group_voters_query.count()
        group_data.append(total_in_group)
        
        # Проголосовавшие в группе с фильтрами
        voted_group_query = Voter.objects.filter(
            uik__in=[item.uik for item in daily_data],
            workplace__group=group,
            confirmed_by_brigadier=True,
            voting_date__isnull=False
        )
        if has_active_filters:
            voted_group_query = voted_group_query.filter(voter_filters)
        voted_in_group = voted_group_query.count()
        group_voted_data.append(voted_in_group)
    
    # Добавляем отдельную группу для агитаторов с фильтрами
    group_labels.append('Агитаторы')
    
    # Общее количество агитаторов с фильтрами
    agitators_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        is_agitator=True
    )
    if has_active_filters:
        agitators_query = agitators_query.filter(voter_filters)
    total_agitators = agitators_query.count()
    group_data.append(total_agitators)
    
    # Проголосовавшие агитаторы с фильтрами
    voted_agitators_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        is_agitator=True,
        confirmed_by_brigadier=True,
        voting_date__isnull=False
    )
    if has_active_filters:
        voted_agitators_query = voted_agitators_query.filter(voter_filters)
    voted_agitators = voted_agitators_query.count()
    group_voted_data.append(voted_agitators)
    
    workplace_groups_data = {
        'labels': group_labels,
        'total_data': group_data,
        'voted_data': group_voted_data,
        'colors': ['#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981', '#f97316', '#84cc16', '#06b6d4']
    }
    
    # 3. Специальная диаграмма для БУЗ ВО "ВГКП № 3" с фильтрами
    vgkp3_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        workplace__name='БУЗ ВО "ВГКП № 3"'
    )
    if has_active_filters:
        vgkp3_query = vgkp3_query.filter(voter_filters)
    vgkp3_total = vgkp3_query.count()
    
    vgkp3_voted_query = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        workplace__name='БУЗ ВО "ВГКП № 3"',
        confirmed_by_brigadier=True,
        voting_date__isnull=False
    )
    if has_active_filters:
        vgkp3_voted_query = vgkp3_voted_query.filter(voter_filters)
    vgkp3_voted = vgkp3_voted_query.count()
    
    vgkp3_data = {
        'labels': ['Проголосовали', 'Осталось по плану'],
        'data': [vgkp3_voted, vgkp3_total - vgkp3_voted],
        'colors': ['#10b981', '#f59e0b'],
        'title': 'БУЗ ВО "ВГКП № 3"'
    }
    
    context.update({
        'total_plan': total_plan,
        'total_fact': total_fact,
        'plan_execution_percent': plan_execution_percent,
        'total_at_uik': total_at_uik,
        'total_at_home': total_at_home,
        'total_plan_12_sep': total_plan_12_sep,
        'total_12_sep': total_12_sep,
        'total_12_sep_uik': total_12_sep_uik,
        'total_12_sep_home': total_12_sep_home,
        'plan_12_percent': plan_12_percent,
        'total_plan_13_sep': total_plan_13_sep,
        'total_13_sep': total_13_sep,
        'total_13_sep_uik': total_13_sep_uik,
        'total_13_sep_home': total_13_sep_home,
        'plan_13_percent': plan_13_percent,
        'total_plan_14_sep': total_plan_14_sep,
        'total_14_sep': total_14_sep,
        'total_14_sep_uik': total_14_sep_uik,
        'total_14_sep_home': total_14_sep_home,
        'plan_14_percent': plan_14_percent,
        'uik_table_data': uik_table_data,
        'last_update_time': last_update_time,
        # Данные для диаграмм
        'voting_status_data': voting_status_data,
        'workplace_groups_data': workplace_groups_data,
        'vgkp3_data': vgkp3_data,
    })
    
    return context


def results_by_brigadiers_dashboard_callback(request, context):
    """Дашборд с группировкой по руководителям (бригадирам)"""
    from .models import User, UIK, Voter
    from django.db.models import Q, Count, Sum
    
    # Получаем ВСЕХ бригадиров, которые работают в системе
    # 1. Основные бригадиры (назначены как brigadier в УИК)
    main_brigadiers = User.objects.filter(
        role='brigadier',
        assigned_uik_as_brigadier__isnull=False
    ).distinct()
    
    # 2. Дополнительные бригадиры (can_be_additional=True и назначены в additional_brigadiers)
    additional_brigadiers = User.objects.filter(
        role='brigadier',
        can_be_additional=True,
        additional_uiks__isnull=False
    ).distinct()
    
    # 3. Бригадиры с назначенными агитаторами (assigned_agitators)
    brigadiers_with_agitators = User.objects.filter(
        role='brigadier',
        assigned_agitators__isnull=False
    ).distinct()
    
    # Объединяем всех бригадиров и сортируем по фамилии
    all_brigadiers = (main_brigadiers | additional_brigadiers | brigadiers_with_agitators).distinct().prefetch_related(
        'assigned_agitators', 
        'assigned_uik_as_brigadier', 
        'additional_uiks'
    ).order_by('last_name', 'first_name', 'middle_name')
    
    rows = []
    total_plan = 0
    total_fact = 0
    total_plan_12_sep = 0
    total_12_sep = 0
    total_plan_13_sep = 0
    total_13_sep = 0
    total_plan_14_sep = 0
    total_14_sep = 0
    
    for brigadier in all_brigadiers:
            
        brigadier_total_plan = 0
        brigadier_total_fact = 0
        brigadier_plan_12_sep = 0
        brigadier_12_sep = 0
        brigadier_plan_13_sep = 0
        brigadier_13_sep = 0
        brigadier_plan_14_sep = 0
        brigadier_14_sep = 0
        
        # Получаем УИК, где работает этот бригадир
        # Используем один запрос с Q объектами для объединения всех условий
        from django.db.models import Q
        
        uiks = UIK.objects.filter(
            Q(brigadier=brigadier) |  # Как основной бригадир
            Q(additional_brigadiers=brigadier) |  # Как дополнительный бригадир
            Q(agitators__in=brigadier.assigned_agitators.all())  # УИК с назначенными агитаторами
        ).distinct().prefetch_related('agitators')
        
    # Сначала собираем все данные по бригадиру
    uik_data = []
    for uik in uiks:
        uik_total_plan = 0
        uik_total_fact = 0
        uik_plan_12_sep = 0
        uik_12_sep = 0
        uik_plan_13_sep = 0
        uik_13_sep = 0
        uik_plan_14_sep = 0
        uik_14_sep = 0
        
        # Агитаторы этого бригадира в этом УИК
        # Логика: 
        # - Если бригадир основной (brigadier=uik.brigadier), то берем агитаторов БЕЗ assigned_brigadiers ИЛИ с assigned_brigadiers=этот_бригадир
        # - Если бригадир дополнительный, то берем агитаторов С assigned_brigadiers=этот_бригадир
        
        if uik.brigadier == brigadier:
            # Основной бригадир - берем агитаторов БЕЗ assigned_brigadiers ИЛИ с assigned_brigadiers=этот_бригадир
            agitators = uik.agitators.filter(
                Q(assigned_brigadiers__isnull=True) | Q(assigned_brigadiers=brigadier)
            ).order_by('last_name', 'first_name', 'middle_name')
        else:
            # Дополнительный бригадир - берем агитаторов С assigned_brigadiers=этот_бригадир
            agitators = uik.agitators.filter(assigned_brigadiers=brigadier).order_by('last_name', 'first_name', 'middle_name')
        
        # Планы для УИК считаем по planned_date (планируемая дата голосования)
        uik_plan_query_12 = Voter.objects.filter(
            uik=uik,
            agitator__in=agitators,
            planned_date=date(2025, 9, 12)
        )
        uik_plan_query_13 = Voter.objects.filter(
            uik=uik,
            agitator__in=agitators,
            planned_date=date(2025, 9, 13)
        )
        uik_plan_query_14 = Voter.objects.filter(
            uik=uik,
            agitator__in=agitators,
            planned_date=date(2025, 9, 14)
        )
        uik_total_plan_query = Voter.objects.filter(
            uik=uik,
            agitator__in=agitators
        )
        
        
        uik_plan_12_sep = uik_plan_query_12.count()
        uik_plan_13_sep = uik_plan_query_13.count()
        uik_plan_14_sep = uik_plan_query_14.count()
        uik_total_plan = uik_total_plan_query.count()
        
        agitator_data = []
        for agitator in agitators:
            # Считаем факты по агитатору
            fact_query_total = Voter.objects.filter(
                uik=uik, 
                agitator=agitator, 
                confirmed_by_brigadier=True
            )
            fact_query_12 = Voter.objects.filter(
                uik=uik, 
                agitator=agitator, 
                confirmed_by_brigadier=True,
                voting_date=date(2025, 9, 12)
            )
            fact_query_13 = Voter.objects.filter(
                uik=uik, 
                agitator=agitator, 
                confirmed_by_brigadier=True,
                voting_date=date(2025, 9, 13)
            )
            fact_query_14 = Voter.objects.filter(
                uik=uik, 
                agitator=agitator, 
                confirmed_by_brigadier=True,
                voting_date=date(2025, 9, 14)
            )
            
            
            fact_total = fact_query_total.count()
            fact_12_sep = fact_query_12.count()
            fact_13_sep = fact_query_13.count()
            fact_14_sep = fact_query_14.count()
            
            # Считаем план агитатора из базы избирателей (все избиратели этого агитатора в этом УИК)
            plan_query_total = Voter.objects.filter(
                uik=uik, 
                agitator=agitator
            )
            plan_query_12 = Voter.objects.filter(
                uik=uik, 
                agitator=agitator,
                planned_date=date(2025, 9, 12)
            )
            plan_query_13 = Voter.objects.filter(
                uik=uik, 
                agitator=agitator,
                planned_date=date(2025, 9, 13)
            )
            plan_query_14 = Voter.objects.filter(
                uik=uik, 
                agitator=agitator,
                planned_date=date(2025, 9, 14)
            )
            
            
            plan_total = plan_query_total.count()
            plan_12_sep = plan_query_12.count()
            plan_13_sep = plan_query_13.count()
            plan_14_sep = plan_query_14.count()
            
            # Процент выполнения плана
            plan_12_percent = round((fact_12_sep / plan_12_sep * 100) if plan_12_sep > 0 else 0, 1)
            plan_13_percent = round((fact_13_sep / plan_13_sep * 100) if plan_13_sep > 0 else 0, 1)
            plan_14_percent = round((fact_14_sep / plan_14_sep * 100) if plan_14_sep > 0 else 0, 1)
            plan_total_percent = round((fact_total / plan_total * 100) if plan_total > 0 else 0, 1)
            
            agitator_data.append({
                'row_type': 'agitator',
                'brigadier': '',  # ПУСТАЯ ячейка для агитатора
                'uik_number': f'|____',  # Символ для агитатора
                'agitator_name': agitator.get_short_name(),
                'fact_total': fact_total,
                'plan_total': plan_total,
                'plan_execution_percent': plan_total_percent,  # ОБЩИЙ ПРОЦЕНТ
                'plan_12_sep': plan_12_sep,
                'fact_12_sep': fact_12_sep,
                'plan_12_percent': plan_12_percent,
                'plan_13_sep': plan_13_sep,
                'fact_13_sep': fact_13_sep,
                'plan_13_percent': plan_13_percent,
                'plan_14_sep': plan_14_sep,
                'fact_14_sep': fact_14_sep,
                'plan_14_percent': plan_14_percent,
            })
            
            uik_total_fact += fact_total
            uik_12_sep += fact_12_sep
            uik_13_sep += fact_13_sep
            uik_14_sep += fact_14_sep
            
            # Сохраняем данные по УИК (если есть план или факт)
            if uik_total_plan > 0 or uik_total_fact > 0:
                
                uik_plan_12_percent = round((uik_12_sep / uik_plan_12_sep * 100) if uik_plan_12_sep > 0 else 0, 1)
                uik_plan_13_percent = round((uik_13_sep / uik_plan_13_sep * 100) if uik_plan_13_sep > 0 else 0, 1)
                uik_plan_14_percent = round((uik_14_sep / uik_plan_14_sep * 100) if uik_plan_14_sep > 0 else 0, 1)
                uik_total_percent = round((uik_total_fact / uik_total_plan * 100) if uik_total_plan > 0 else 0, 1)
                
                uik_data.append({
                    'uik_info': {
                        'row_type': 'uik_total',
                        'brigadier': '|_______',  # Символ для УИК
                        'uik_number': f'L{uik.number}',  # Галка в УИК
                        'agitator_name': f'Итого по УИК {uik.number}',
                        'fact_total': uik_total_fact,
                        'plan_total': uik_total_plan,
                        'plan_execution_percent': uik_total_percent,
                        'plan_12_sep': uik_plan_12_sep,
                        'fact_12_sep': uik_12_sep,
                        'plan_12_percent': uik_plan_12_percent,
                        'plan_13_sep': uik_plan_13_sep,
                        'fact_13_sep': uik_13_sep,
                        'plan_13_percent': uik_plan_13_percent,
                        'plan_14_sep': uik_plan_14_sep,
                        'fact_14_sep': uik_14_sep,
                        'plan_14_percent': uik_plan_14_percent,
                    },
                    'agitators': agitator_data
                })
                
                brigadier_total_fact += uik_total_fact
                brigadier_total_plan += uik_total_plan
                brigadier_12_sep += uik_12_sep
                brigadier_13_sep += uik_13_sep
                brigadier_14_sep += uik_14_sep
                brigadier_plan_12_sep += uik_plan_12_sep
                brigadier_plan_13_sep += uik_plan_13_sep
                brigadier_plan_14_sep += uik_plan_14_sep
        
        # Добавляем строку бригадира (если есть план или факт)
        if brigadier_total_plan > 0 or brigadier_total_fact > 0:
            
            brigadier_plan_12_percent = round((brigadier_12_sep / brigadier_plan_12_sep * 100) if brigadier_plan_12_sep > 0 else 0, 1)
            brigadier_plan_13_percent = round((brigadier_13_sep / brigadier_plan_13_sep * 100) if brigadier_plan_13_sep > 0 else 0, 1)
            brigadier_plan_14_percent = round((brigadier_14_sep / brigadier_plan_14_sep * 100) if brigadier_plan_14_sep > 0 else 0, 1)
            brigadier_total_percent = round((brigadier_total_fact / brigadier_total_plan * 100) if brigadier_total_plan > 0 else 0, 1)
            
            # Строка бригадира
            rows.append({
                'row_type': 'brigadier_total',
                'brigadier': brigadier.get_short_name(),  # ИМЯ БРИГАДИРА
                'uik_number': '',  # ПУСТОЙ для бригадира
                'agitator_name': f'ИТОГО по {brigadier.get_short_name()}',
                'fact_total': brigadier_total_fact,
                'plan_total': brigadier_total_plan,
                'plan_execution_percent': brigadier_total_percent,
                'plan_12_sep': brigadier_plan_12_sep,
                'fact_12_sep': brigadier_12_sep,
                'plan_12_percent': brigadier_plan_12_percent,
                'plan_13_sep': brigadier_plan_13_sep,
                'fact_13_sep': brigadier_13_sep,
                'plan_13_percent': brigadier_plan_13_percent,
                'plan_14_sep': brigadier_plan_14_sep,
                'fact_14_sep': brigadier_14_sep,
                'plan_14_percent': brigadier_plan_14_percent,
            })
            
            # Добавляем данные по УИК и агитаторам
            for uik_item in uik_data:
                # Строка УИК
                rows.append(uik_item['uik_info'])
                # Строки агитаторов
                rows.extend(uik_item['agitators'])
            
            total_fact += brigadier_total_fact
            total_plan += brigadier_total_plan
            total_12_sep += brigadier_12_sep
            total_13_sep += brigadier_13_sep
            total_14_sep += brigadier_14_sep
            total_plan_12_sep += brigadier_plan_12_sep
            total_plan_13_sep += brigadier_plan_13_sep
            total_plan_14_sep += brigadier_plan_14_sep
    
    # Общие итоги
    plan_execution_percent = round((total_fact / total_plan * 100) if total_plan > 0 else 0, 1)
    plan_12_percent = round((total_12_sep / total_plan_12_sep * 100) if total_plan_12_sep > 0 else 0, 1)
    plan_13_percent = round((total_13_sep / total_plan_13_sep * 100) if total_plan_13_sep > 0 else 0, 1)
    plan_14_percent = round((total_14_sep / total_plan_14_sep * 100) if total_plan_14_sep > 0 else 0, 1)
    
    context.update({
        'brigadier_rows': rows,
        'total_plan': total_plan,
        'total_fact': total_fact,
        'plan_execution_percent': plan_execution_percent,
        'total_plan_12_sep': total_plan_12_sep,
        'total_12_sep': total_12_sep,
        'plan_12_percent': plan_12_percent,
        'total_plan_13_sep': total_plan_13_sep,
        'total_13_sep': total_13_sep,
        'plan_13_percent': plan_13_percent,
        'total_plan_14_sep': total_plan_14_sep,
        'total_14_sep': total_14_sep,
        'plan_14_percent': plan_14_percent,
    })
    
    return context