"""
URL configuration for elections_system project.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from elections.views import dashboard_view, get_uik_agitators

def redirect_to_admin(request):
    """Редирект корневого URL на админку"""
    return redirect('/admin/')

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('admin/elections/voter/<int:voter_id>/get_uik_agitators/', get_uik_agitators, name='get_uik_agitators'),
    path('admin/', admin.site.urls),
    path('', redirect_to_admin),  # Корневой URL редиректит на админку
]

# Статические файлы для разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
