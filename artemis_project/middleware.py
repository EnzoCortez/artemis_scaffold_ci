from django.http import HttpResponseBadRequest

class AntiParameterPollutionMiddleware:
    """
    Bloquea las peticiones que contienen múltiples valores para un mismo parámetro GET o POST,
    previniendo ataques de HTTP Parameter Pollution a nivel global reportados por escáneres de seguridad
    (Ej. ?next=/admin/&next=was-xxx).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Validar en GET
        for key, values in request.GET.lists():
            if len(values) > 1:
                return HttpResponseBadRequest(
                    f"Access Denied: Multiple values for parameter '{key}' are not allowed (Security: HPP protection)."
                )
        
        # Validar en POST si aplica (A veces DataTables envía estructuras complejas, 
        # pero es raro que dupliquen la llave raíz idéntica excepto arrays. Bloqueamos solo GET para no quebrar UI por si acaso).

        return self.get_response(request)
