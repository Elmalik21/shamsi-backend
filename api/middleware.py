# api/middleware.py
import time
import json
from django.utils import timezone
from .models import APILog, APIConfig

class APILoggingMiddleware:
    """
    Middleware to log all API requests and responses to the APILog model.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # We only log requests going to API endpoints
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Get start time
        start_time = time.time()

        # Parse request body safely
        request_data = None
        if request.method in ('POST', 'PUT', 'PATCH'):
            try:
                if request.content_type == 'application/json':
                    body_content = request.body.decode('utf-8')
                    request_data = json.loads(body_content)
                else:
                    request_data = dict(request.POST)
            except Exception:
                pass

        # Execute request
        response = self.get_response(request)

        # Calculate duration in ms
        duration_ms = (time.time() - start_time) * 1000.0

        # Parse response body safely
        response_data = None
        if hasattr(response, 'data') and isinstance(response.data, (dict, list)):
            response_data = response.data
        elif hasattr(response, 'content'):
            try:
                response_data = json.loads(response.content.decode('utf-8'))
            except Exception:
                pass

        # Extract client details
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        user_id = str(request.user.id) if request.user.is_authenticated else None

        # Resolve config type based on path
        config_type = 'GENERAL'
        if 'climate' in request.path:
            config_type = 'CLIMATE'
        elif 'solar' in request.path or 'optimize' in request.path:
            config_type = 'SOLAR'
        elif 'tariffs' in request.path:
            config_type = 'PRICE'

        api_config = APIConfig.objects.filter(config_type=config_type, is_active=True).first()

        try:
            APILog.objects.create(
                endpoint=request.path,
                method=request.method,
                request_data=request_data,
                status_code=response.status_code,
                response_data=response_data,
                response_time=duration_ms,
                ip_address=ip_address,
                user_agent=user_agent,
                user_id=user_id,
                api_config=api_config
            )
        except Exception:
            # Prevent logging database issues from breaking the API response
            pass

        return response
