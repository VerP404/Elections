from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class AdminOnlyMiddleware(MiddlewareMixin):
    """
    Middleware для редиректа всех запросов на админку
    """
    
    def process_request(self, request):
        """
        Проверяем все входящие запросы и редиректим на админку если необходимо
        """
        # Разрешенные пути (админка, статические файлы, медиа, дашборд)
        allowed_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/dashboard/',
        ]
        
        # Проверяем, начинается ли путь с разрешенных
        path = request.path
        
        # Если это корневой путь - редиректим на админку
        if path == '/':
            return redirect('/admin/')
        
        # Если путь не начинается с разрешенных - редиректим на админку
        if not any(path.startswith(allowed_path) for allowed_path in allowed_paths):
            return redirect('/admin/')
        
        # Для всех разрешенных путей - пропускаем
        return None 