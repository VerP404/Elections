from django.shortcuts import redirect
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.html import format_html


class AdminOnlyMiddleware:
    """Middleware для редиректа на админку"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Пути, которые разрешены вне админки
        self.allowed_paths = [
            '/admin/',
            '/admin/login/',
            '/admin/logout/',
            '/dashboard/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]
    
    def __call__(self, request):
        # Проверяем, нужно ли перенаправлять на админку
        if not any(request.path.startswith(path) for path in self.allowed_paths):
            return redirect('/admin/')
        
        response = self.get_response(request)
        return response


class PermissionDeniedMiddleware:
    """Middleware для обработки PermissionDenied с красивыми уведомлениями"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """Обрабатываем PermissionDenied исключения"""
        if isinstance(exception, PermissionDenied):
            # Добавляем красивое сообщение
            messages.error(
                request,
                format_html(
                    '<div style="text-align: center; padding: 20px;">'
                    '<h3 style="color: #d32f2f; margin-bottom: 10px;">⚠️ Недостаточно прав</h3>'
                    '<p style="color: #666; font-size: 16px;">'
                    'У вас нет прав для доступа к этой странице. '
                    'Обратитесь к администратору системы.'
                    '</p>'
                    '<p style="margin-top: 15px;">'
                    '<a href="/admin/" style="background: #1976d2; color: white; '
                    'padding: 10px 20px; text-decoration: none; border-radius: 4px;">'
                    'Вернуться в админку</a>'
                    '</p>'
                    '</div>'
                )
            )
            
            # Перенаправляем на главную страницу админки
            from django.shortcuts import redirect
            return redirect('/admin/')
        
        return None 