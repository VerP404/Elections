from django.db.models import Count, Q, Sum
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminDecimalFieldWidget
from .models import UIK, Voter, User, UIKResults, UIKAnalysis, PlannedVoter, VotingRecord
import plotly.graph_objs as go
import plotly.offline as pyo


def dashboard_callback(request, context):
    """Callback для дашборда с графиками"""
    # Получаем данные для графиков по новой логике
    uik_data = UIK.objects.annotate(
        planned_voters_annotated=Count('voter__plannedvoter', distinct=True),
        confirmed_voters_count=Count('voter__plannedvoter__votingrecord', filter=Q(voter__plannedvoter__votingrecord__confirmed_by_brigadier=True), distinct=True)
    ).values('number', 'planned_voters_annotated', 'confirmed_voters_count')
    
    # Данные для первого графика (планируемые vs подтвержденные)
    planned_vs_confirmed = []
    for uik in uik_data:
            planned_vs_confirmed.append({
        'uik': f"УИК №{uik['number']}",
        'planned': uik['planned_voters_annotated'],
        'confirmed': uik['confirmed_voters_count'],
        'percentage': round((uik['confirmed_voters_count'] / uik['planned_voters_annotated'] * 100), 1) if uik['planned_voters_annotated'] > 0 else 0
    })
    
    # Данные для второго графика (способы голосования)
    voting_methods = []
    for uik in uik_data:
        # Получаем данные о способах голосования
        voting_records = VotingRecord.objects.filter(
            planned_voter__voter__uik__number=uik['number']
        ).values('voting_method').annotate(count=Count('id'))
        
        ballot_box = next((item['count'] for item in voting_records if item['voting_method'] == 'ballot_box'), 0)
        koib = next((item['count'] for item in voting_records if item['voting_method'] == 'koib'), 0)
        independent = next((item['count'] for item in voting_records if item['voting_method'] == 'independent'), 0)
        
        voting_methods.append({
            'uik': f"УИК №{uik['number']}",
            'ballot_box': ballot_box,
            'koib': koib,
            'independent': independent,
            'total': ballot_box + koib + independent
        })
    
    # Проверяем есть ли данные
    if not planned_vs_confirmed:
        context.update({
            'plot1': '<div class="alert alert-info">Нет данных для отображения</div>',
            'plot2': '<div class="alert alert-info">Нет данных для отображения</div>',
        })
        return context
    
    # Создаем графики
    fig1 = go.Figure()
    
    # Первый график - плановое vs подтвержденное
    uik_names = [item['uik'] for item in planned_vs_confirmed]
    planned_values = [item['planned'] for item in planned_vs_confirmed]
    confirmed_values = [item['confirmed'] for item in planned_vs_confirmed]
    
    fig1.add_trace(go.Bar(
        name='Плановое число',
        x=uik_names,
        y=planned_values,
        marker_color='#3b82f6',
        opacity=0.8
    ))
    
    fig1.add_trace(go.Bar(
        name='Подтверждено',
        x=uik_names,
        y=confirmed_values,
        marker_color='#10b981',
        opacity=0.8
    ))
    
    fig1.update_layout(
        title='Плановое vs Подтвержденное количество избирателей по УИК',
        xaxis_title='УИК',
        yaxis_title='Количество избирателей',
        barmode='group',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    fig1.update_xaxes(tickangle=45)
    
    # Второй график - способы голосования
    fig2 = go.Figure()
    
    ballot_box_values = [item['ballot_box'] for item in voting_methods]
    koib_values = [item['koib'] for item in voting_methods]
    independent_values = [item['independent'] for item in voting_methods]
    
    fig2.add_trace(go.Bar(
        name='Урна',
        x=uik_names,
        y=ballot_box_values,
        marker_color='#ef4444',
        opacity=0.8
    ))
    
    fig2.add_trace(go.Bar(
        name='КОИБ',
        x=uik_names,
        y=koib_values,
        marker_color='#f59e0b',
        opacity=0.8
    ))
    
    fig2.add_trace(go.Bar(
        name='Самостоятельно',
        x=uik_names,
        y=independent_values,
        marker_color='#8b5cf6',
        opacity=0.8
    ))
    
    fig2.update_layout(
        title='Распределение способов голосования по УИК',
        xaxis_title='УИК',
        yaxis_title='Количество избирателей',
        barmode='group',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    fig2.update_xaxes(tickangle=45)
    
    # Конвертируем графики в HTML
    plot1_html = pyo.plot(fig1, output_type='div', include_plotlyjs=False)
    plot2_html = pyo.plot(fig2, output_type='div', include_plotlyjs=False)
    
    context.update({
        'plot1': plot1_html,
        'plot2': plot2_html,
    })
    
    return context

def user_dashboard_callback(request, context):
    """Callback для персональной главной панели пользователя"""
    user = request.user
    
    # Получаем статистику пользователя
    user_stats = get_user_statistics(user)
    
    context.update({
        'user_stats': user_stats,
    })
    
    return context

def get_user_statistics(user):
    """Получение персональной статистики пользователя с учетом ролей"""
    # Определяем какие записи видит пользователь в зависимости от роли
    if user.is_superuser or user.role == 'admin':
        # Админ видит все записи
        planned_voters = PlannedVoter.objects.all()
        total_voters = Voter.objects.count()
    elif user.role == 'brigadier':
        # Бригадир видит записи своих агитаторов
        planned_voters = PlannedVoter.objects.filter(agitator__brigadier=user)
        total_voters = Voter.objects.count()
    elif user.role == 'agitator':
        # Агитатор видит только свои записи
        planned_voters = PlannedVoter.objects.filter(agitator=user)
        total_voters = Voter.objects.count()
    else:
        # По умолчанию - только свои записи
        planned_voters = PlannedVoter.objects.filter(agitator=user)
        total_voters = Voter.objects.count()
    
    # Количество планируемых избирателей
    voters_planned = planned_voters.count()
    
    # Подтвержденные избиратели
    voters_confirmed = planned_voters.filter(votingrecord__confirmed_by_brigadier=True).count()
    
    # Избиратели с записанным голосованием
    voters_with_records = planned_voters.filter(votingrecord__isnull=False).count()
    
    # Процент от общего количества
    voters_percentage = round((voters_planned / total_voters * 100), 1) if total_voters > 0 else 0
    
    # Эффективность (процент подтвержденных от планируемых)
    efficiency = round((voters_confirmed / voters_planned * 100), 1) if voters_planned > 0 else 0
    
    return {
        'voters_planned': voters_planned,
        'voters_confirmed': voters_confirmed,
        'voters_with_records': voters_with_records,
        'voters_percentage': voters_percentage,
        'efficiency': efficiency,
        'role': user.role,
    }


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
        })
        return context
    
    # Общая статистика по УИК
    total_uiks = analysis_data.count()
    completed_uiks = sum(1 for analysis in analysis_data if analysis.plan_execution_percentage >= 100)
    
    # Статистика по избирателям
    total_planned_voters = sum(analysis.total_plan for analysis in analysis_data)
    total_confirmed_voters = sum(analysis.total_fact for analysis in analysis_data)
    voters_percentage = round((total_confirmed_voters / total_planned_voters * 100), 1) if total_planned_voters > 0 else 0
    
    # Данные для таблицы УИК
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
    from django.utils import timezone
    last_update = UIKAnalysis.objects.order_by('-updated_at').first()
    last_update_time = last_update.updated_at if last_update else timezone.now()
    
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