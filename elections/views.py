from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .dashboard import (
    analysis_dashboard_callback,
    results_dashboard_callback,
    results_table_dashboard_callback,
)
from .models import Voter, User, UIK

# Create your views here.

@login_required(login_url='/admin/login/')
def analysis_dashboard_view(request):
    """View для дашборда анализа по УИК"""
    context = analysis_dashboard_callback(request, {})
    return render(request, 'admin/analysis_dashboard.html', context)

@login_required(login_url='/admin/login/')
def results_dashboard_view(request):
    """View для дашборда результатов голосования"""
    context = results_dashboard_callback(request, {})
    return render(request, 'admin/results_dashboard.html', context)

@login_required(login_url='/admin/login/')
def results_table_dashboard_view(request):
    """Табличный дашборд с расчетом фактов по подтвержденным голосованиям."""
    context = results_table_dashboard_callback(request, {})
    return render(request, 'admin/results_table_dashboard.html', context)

@login_required(login_url='/admin/login/')
def get_uik_agitators(request, voter_id):
    """AJAX endpoint для получения агитаторов УИК выбранного избирателя"""
    try:
        voter = get_object_or_404(Voter, id=voter_id)
        uik = voter.uik
        
        # Получаем агитаторов УИК
        agitators = User.objects.filter(
            role='agitator',
            is_active_participant=True,
            assigned_uiks_as_agitator=uik
        ).values('id', 'first_name', 'last_name', 'middle_name')
        
        # Формируем полные имена
        agitators_list = []
        for agitator in agitators:
            full_name = f"{agitator['last_name']} {agitator['first_name']}"
            if agitator['middle_name']:
                full_name += f" {agitator['middle_name']}"
            
            agitators_list.append({
                'id': agitator['id'],
                'full_name': full_name
            })
        
        return JsonResponse({
            'success': True,
            'agitators': agitators_list
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required(login_url='/admin/login/')
def get_agitator_uik(request, user_id):
    """API endpoint для получения УИК агитатора"""
    try:
        user = User.objects.get(id=user_id, role='agitator')
        
        # Получаем первый УИК, где работает агитатор
        uik = user.assigned_uiks_as_agitator.first()
        
        if uik:
            return JsonResponse({'uik_id': uik.id, 'uik_number': uik.number})
        else:
            return JsonResponse({'error': 'Агитатор не назначен ни на один УИК'}, status=404)
            
    except User.DoesNotExist:
        return JsonResponse({'error': 'Пользователь не найден или не является агитатором'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)