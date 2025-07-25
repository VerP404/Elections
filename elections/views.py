from django.shortcuts import render
from .dashboard import dashboard_callback
from django.contrib.auth.decorators import login_required

# Create your views here.

@login_required(login_url='/admin/login/')
def dashboard_view(request):
    context = dashboard_callback(request, {})
    return render(request, 'admin/dashboard.html', context)
