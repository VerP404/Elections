from django.db.models import Count, Q, Sum
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminDecimalFieldWidget
from .models import UIK, Voter, Participant, UIKResults
import plotly.graph_objs as go
from plotly.offline import plot


def dashboard_callback(request, context):
    """
    Функция обратного вызова для дашборда администратора
    """
    
    # Статистика по УИК
    uik_stats = {
        'total_uik': UIK.objects.count(),
        'uik_with_results': UIKResults.objects.exclude(
            ballot_box_votes=0, koib_votes=0, independent_votes=0
        ).count(),
    }
    
    # Статистика по избирателям
    voter_stats = {
        'total_voters': Voter.objects.count(),
        'voters_with_phone': Voter.objects.exclude(phone_number='').count(),
        'voters_confirmed': Voter.objects.filter(voting_confirmed=True).count(),
        'voters_with_agitator': Voter.objects.exclude(agitator__isnull=True).count(),
        'voters_with_brigadier': Voter.objects.exclude(brigadier__isnull=True).count(),
    }
    
    # Статистика по участникам
    participant_stats = {
        'total_participants': Participant.objects.filter(is_active=True).count(),
        'agitators': Participant.objects.filter(
            role__in=['agitator', 'both'], is_active=True
        ).count(),
        'brigadiers': Participant.objects.filter(
            role__in=['brigadier', 'both'], is_active=True
        ).count(),
    }
    
    # Статистика по результатам голосования
    voting_results = UIKResults.objects.aggregate(
        total_ballot_box=Sum('ballot_box_votes'),
        total_koib=Sum('koib_votes'),
        total_independent=Sum('independent_votes'),
    )
    
    total_votes = sum(filter(None, voting_results.values()))
    
    # Топ УИК по количеству избирателей
    top_uik = UIK.objects.annotate(
        voters_count=Count('voter')
    ).order_by('-voters_count')[:5]
    
    # Топ агитаторов
    top_agitators = Participant.objects.filter(
        role__in=['agitator', 'both'], is_active=True
    ).annotate(
        agitated_count=Count('agitated_voters')
    ).order_by('-agitated_count')[:5]
    
    # Процент проголосовавших по УИК
    uik_voting_stats = []
    for uik in UIK.objects.all()[:10]:  # Ограничиваем для производительности
        total_voters = uik.voter_set.count()
        confirmed_voters = uik.voter_set.filter(voting_confirmed=True).count()
        percentage = (confirmed_voters / total_voters * 100) if total_voters > 0 else 0
        uik_voting_stats.append({
            'uik': uik,
            'total_voters': total_voters,
            'confirmed_voters': confirmed_voters,
            'percentage': round(percentage, 1)
        })
    
    # --- График 1: Плановое и учтённые по УИК ---
    uik_labels = []
    planned = []
    confirmed = []
    for uik in UIK.objects.all().order_by('number'):
        uik_labels.append(f"УИК №{uik.number}")
        planned.append(uik.planned_voters_count)
        res = getattr(uik, 'uikresults', None)
        if res:
            confirmed.append(res.confirmed_voters_count)
        else:
            confirmed.append(0)
    bar1 = go.Bar(name='План', x=uik_labels, y=planned)
    bar2 = go.Bar(name='Учт.', x=uik_labels, y=confirmed)
    fig1 = go.Figure(data=[bar1, bar2])
    fig1.update_layout(
        barmode='group',
        title='Плановое и учтённые по УИК',
        xaxis_title='УИК',
        yaxis_title='Число избирателей',
        autosize=True,
        width=None,
        height=500,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.15,
            xanchor='center', x=0.5,
            font=dict(size=10),
        ),
        xaxis=dict(tickangle=60, tickfont=dict(size=10)),
    )
    plot1_html = plot(fig1, output_type='div', include_plotlyjs='cdn', config={'responsive': True})

    # --- График 2: Урна, КОИБ, Самостоятельно по УИК ---
    ballot_box = []
    koib = []
    independent = []
    total_votes = []
    for uik in UIK.objects.all().order_by('number'):
        res = getattr(uik, 'uikresults', None)
        if res:
            ballot_box.append(res.ballot_box_votes)
            koib.append(res.koib_votes)
            independent.append(res.independent_votes)
            total_votes.append(res.total_votes)
        else:
            ballot_box.append(0)
            koib.append(0)
            independent.append(0)
            total_votes.append(0)
    bar3 = go.Bar(name='Урна', x=uik_labels, y=ballot_box)
    bar4 = go.Bar(name='КОИБ', x=uik_labels, y=koib)
    bar5 = go.Bar(name='Самост.', x=uik_labels, y=independent)
    fig2 = go.Figure(data=[bar3, bar4, bar5])
    fig2.update_layout(
        barmode='group',
        title='Голоса по способу голосования',
        xaxis_title='УИК',
        yaxis_title='Число голосов',
        autosize=True,
        width=None,
        height=500,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.15,
            xanchor='center', x=0.5,
            font=dict(size=10),
        ),
        xaxis=dict(tickangle=60, tickfont=dict(size=10)),
    )
    # Добавляем подписи "Всего голосов" под графиком
    total_votes_text = '<br>'.join([f'{label}: {val}' for label, val in zip(uik_labels, total_votes)])
    plot2_html = plot(fig2, output_type='div', include_plotlyjs=False, config={'responsive': True})

    context['uik_dashboard_plot1'] = plot1_html
    context['uik_dashboard_plot2'] = plot2_html
    context['uik_dashboard_total_votes'] = total_votes_text

    context.update({
        'uik_stats': uik_stats,
        'voter_stats': voter_stats,
        'participant_stats': participant_stats,
        'voting_results': voting_results,
        'total_votes': total_votes,
        'top_uik': top_uik,
        'top_agitators': top_agitators,
        'uik_voting_stats': uik_voting_stats,
    })
    
    return context 