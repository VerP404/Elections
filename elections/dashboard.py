
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


def results_dashboard_callback(request, context):
    """Callback для дашборда результатов голосования"""
    # Получаем данные по дням из UIKResultsDaily
    daily_data = UIKResultsDaily.objects.select_related('uik').all()
    
    if not daily_data.exists():
        context.update({
            'total_plan': 0,
            'total_fact': 0,
            'plan_execution_percent': 0,
            'total_plan_12_sep': 0,
            'total_12_sep': 0,
            'plan_12_percent': 0,
            'total_plan_13_sep': 0,
            'total_13_sep': 0,
            'plan_13_percent': 0,
            'total_plan_14_sep': 0,
            'total_14_sep': 0,
            'plan_14_percent': 0,
            'uik_table_data': [],
        })
        return context
    
    # Общая статистика
    total_plan = sum(item.total_plan for item in daily_data)
    total_fact = sum(item.total_fact for item in daily_data)
    plan_execution_percent = round((total_fact / total_plan * 100), 1) if total_plan > 0 else 0
    
    # Подсчет голосов по способам из новой модели Voter
    from datetime import date
    
    # Общий подсчет голосов В УИК (подтвержденных)
    total_at_uik = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        voting_method='at_uik',
        confirmed_by_brigadier=True,
        voting_date__isnull=False
    ).count()
    
    # На дому = общий факт - В УИК
    total_at_home = total_fact - total_at_uik
    
    # Статистика по дням
    total_plan_12_sep = sum(item.plan_12_sep for item in daily_data)
    total_12_sep = sum(item.get_effective_fact_12_sep() for item in daily_data)  # Используем эффективные факты
    plan_12_percent = round((total_12_sep / total_plan_12_sep * 100), 1) if total_plan_12_sep > 0 else 0
    print(f"DEBUG: total_plan_12_sep = {total_plan_12_sep}, total_12_sep = {total_12_sep}, plan_12_percent = {plan_12_percent}")
    
    total_plan_13_sep = sum(item.plan_13_sep for item in daily_data)
    total_13_sep = sum(item.get_effective_fact_13_sep() for item in daily_data)  # Используем эффективные факты
    plan_13_percent = round((total_13_sep / total_plan_13_sep * 100), 1) if total_plan_13_sep > 0 else 0
    
    total_plan_14_sep = sum(item.plan_14_sep for item in daily_data)
    total_14_sep = sum(item.get_effective_fact_14_sep() for item in daily_data)  # Используем эффективные факты
    plan_14_percent = round((total_14_sep / total_plan_14_sep * 100), 1) if total_plan_14_sep > 0 else 0
    
    # Данные для таблицы
    uik_table_data = []
    for item in daily_data:
        execution_percent = item.plan_execution_percentage
        
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
        uik_plan_12_percent = round((item.get_effective_fact_12_sep() / item.plan_12_sep * 100), 1) if item.plan_12_sep > 0 else 0
        uik_plan_13_percent = round((item.get_effective_fact_13_sep() / item.plan_13_sep * 100), 1) if item.plan_13_sep > 0 else 0
        uik_plan_14_percent = round((item.get_effective_fact_14_sep() / item.plan_14_sep * 100), 1) if item.plan_14_sep > 0 else 0
        
        uik_table_data.append({
            'uik_number': item.uik.number,
            'plan_total': item.total_plan,
            'fact_total': item.total_fact,
            'plan_execution_percent': execution_percent,
            'row_color': row_color,
            'plan_12_sep': item.plan_12_sep,
            'fact_12_sep': item.get_effective_fact_12_sep(),
            'plan_12_percent': uik_plan_12_percent,
            'plan_13_sep': item.plan_13_sep,
            'fact_13_sep': item.get_effective_fact_13_sep(),
            'plan_13_percent': uik_plan_13_percent,
            'plan_14_sep': item.plan_14_sep,
            'fact_14_sep': item.get_effective_fact_14_sep(),
            'plan_14_percent': uik_plan_14_percent,
        })
    
    # Сортируем по номеру УИК
    uik_table_data.sort(key=lambda x: x['uik_number'])
    
    # Данные для диаграмм
    # 1. Статус голосования (на основе UIKResultsDaily: Общий план и Общий факт)
    voting_status_data = {
        'labels': ['Проголосовали', 'Осталось по плану'],
        'data': [total_fact, total_plan - total_fact],
        'colors': ['#10b981', '#f59e0b']
    }
    
    # 2. Голосование по всем группам (исключая 'other')
    workplace_groups = [choice[0] for choice in Workplace.GROUP_CHOICES if choice[0] != 'other']
    group_data = []
    group_voted_data = []
    group_labels = []
    
    for group in workplace_groups:
        group_name = dict(Workplace.GROUP_CHOICES).get(group, group)
        group_labels.append(group_name)
        
        # Общее количество в группе
        total_in_group = Voter.objects.filter(
            uik__in=[item.uik for item in daily_data],
            workplace__group=group
        ).count()
        group_data.append(total_in_group)
        
        # Проголосовавшие в группе
        voted_in_group = Voter.objects.filter(
            uik__in=[item.uik for item in daily_data],
            workplace__group=group,
            confirmed_by_brigadier=True,
            voting_date__isnull=False
        ).count()
        group_voted_data.append(voted_in_group)
    
    workplace_groups_data = {
        'labels': group_labels,
        'total_data': group_data,
        'voted_data': group_voted_data,
        'colors': ['#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981', '#f97316', '#84cc16', '#06b6d4']
    }
    
    # 3. Специальная диаграмма для БУЗ ВО "ВГКП № 3"
    vgkp3_total = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        workplace__name='БУЗ ВО "ВГКП № 3"'
    ).count()
    
    vgkp3_voted = Voter.objects.filter(
        uik__in=[item.uik for item in daily_data],
        workplace__name='БУЗ ВО "ВГКП № 3"',
        confirmed_by_brigadier=True,
        voting_date__isnull=False
    ).count()
    
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
        'plan_12_percent': plan_12_percent,
        'total_plan_13_sep': total_plan_13_sep,
        'total_13_sep': total_13_sep,
        'plan_13_percent': plan_13_percent,
        'total_plan_14_sep': total_plan_14_sep,
        'total_14_sep': total_14_sep,
        'plan_14_percent': plan_14_percent,
        'uik_table_data': uik_table_data,
        # Данные для диаграмм
        'voting_status_data': voting_status_data,
        'workplace_groups_data': workplace_groups_data,
        'vgkp3_data': vgkp3_data,
    })
    
    return context