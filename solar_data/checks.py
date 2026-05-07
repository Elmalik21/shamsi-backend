# solar_data/checks.py
"""
System checks for Solar Data Management System
"""
from django.core.checks import register, Error, Warning, Info
from django.conf import settings
from django.db import connection
import os


@register()
def check_data_integrity(app_configs, **kwargs):
    """
    Check data integrity and consistency
    """
    errors = []
    
    try:
        from .models import Location, DailyClimateData, MonthlySummary
        
        # Check for locations without governorate
        locations_without_governorate = Location.objects.filter(governorate__isnull=True).count()
        if locations_without_governorate > 0:
            errors.append(
                Warning(
                    f'{locations_without_governorate} locations without governorate assignment',
                    hint='Assign governorates to all locations for better organization',
                    id='solar_data.W001'
                )
            )
        
        # Check for duplicate location IDs
        from django.db.models import Count
        duplicate_locations = Location.objects.values('location_id').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicate_locations.exists():
            errors.append(
                Error(
                    f'Found {duplicate_locations.count()} duplicate location IDs',
                    hint='Ensure each location has a unique location_id',
                    id='solar_data.E001'
                )
            )
        
        # Check for climate data without location
        orphaned_climate_data = DailyClimateData.objects.filter(location__isnull=True).count()
        if orphaned_climate_data > 0:
            errors.append(
                Error(
                    f'Found {orphaned_climate_data} climate data records without location',
                    hint='Clean up orphaned climate data records',
                    id='solar_data.E002'
                )
            )
        
        # Check for invalid solar potential scores
        invalid_scores = Location.objects.filter(
            solar_potential_score__lt=0
        ) | Location.objects.filter(
            solar_potential_score__gt=100
        )
        
        if invalid_scores.exists():
            errors.append(
                Error(
                    f'Found {invalid_scores.count()} locations with invalid solar potential scores',
                    hint='Solar potential scores must be between 0 and 100',
                    id='solar_data.E003'
                )
            )
        
        # Check for missing calculated fields
        locations_without_stats = Location.objects.filter(
            avg_solar_radiation__isnull=True
        ) | Location.objects.filter(
            avg_temperature__isnull=True
        )
        
        if locations_without_stats.exists():
            errors.append(
                Warning(
                    f'Found {locations_without_stats.count()} locations without calculated statistics',
                    hint='Run location.calculate_statistics() to update missing values',
                    id='solar_data.W002'
                )
            )
        
        # Check database indexes (PostgreSQL only — skip on SQLite)
        db_engine = connection.settings_dict.get('ENGINE', '')
        if 'postgresql' in db_engine:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename LIKE 'solar_data_%'
                    AND indexname NOT LIKE '%pkey'
                """)
                index_count = cursor.fetchone()[0]

                if index_count < 10:
                    errors.append(
                        Warning(
                            f'Found only {index_count} database indexes',
                            hint='Add indexes to frequently queried fields for better performance',
                            id='solar_data.W003'
                        )
                    )
        
        # Check cache configuration
        if not hasattr(settings, 'CACHES') or 'default' not in settings.CACHES:
            errors.append(
                Warning(
                    'Cache not configured',
                    hint='Configure Django cache for better performance',
                    id='solar_data.W004'
                )
            )
        
        # Check for sufficient data
        total_locations = Location.objects.count()
        total_climate_data = DailyClimateData.objects.count()
        
        if total_locations == 0:
            errors.append(
                Info(
                    'No locations in database',
                    hint='Import location data to start using the system',
                    id='solar_data.I001'
                )
            )
        
        if total_climate_data == 0:
            errors.append(
                Info(
                    'No climate data in database',
                    hint='Import climate data for solar potential analysis',
                    id='solar_data.I002'
                )
            )
        
        # Calculate data coverage
        if total_locations > 0 and total_climate_data > 0:
            avg_data_per_location = total_climate_data / total_locations
            if avg_data_per_location < 30:  # Less than 30 days of data per location
                errors.append(
                    Warning(
                        f'Low data coverage: {avg_data_per_location:.1f} days per location on average',
                        hint='Import more climate data for accurate analysis',
                        id='solar_data.W005'
                    )
                )
        
    except Exception as e:
        errors.append(
            Error(
                f'Error during data integrity check: {str(e)}',
                hint='Check database connection and model definitions',
                id='solar_data.E999'
            )
        )
    
    return errors


@register()
def check_model_configurations(app_configs, **kwargs):
    """
    Check model configurations and settings
    """
    errors = []
    
    try:
        from .models import Governorate, Location, DailyClimateData, MonthlySummary
        
        # Check model field configurations
        models_to_check = [Governorate, Location, DailyClimateData, MonthlySummary]
        
        for model in models_to_check:
            # Check for missing verbose names
            if not hasattr(model._meta, 'verbose_name') or not model._meta.verbose_name:
                errors.append(
                    Warning(
                        f'Model {model.__name__} missing verbose_name',
                        hint='Add verbose_name to model Meta class',
                        id='solar_data.W101'
                    )
                )
            
            # Check for missing ordering
            if not hasattr(model._meta, 'ordering') or not model._meta.ordering:
                errors.append(
                    Info(
                        f'Model {model.__name__} missing default ordering',
                        hint='Add ordering to model Meta class for consistent queries',
                        id='solar_data.I101'
                    )
                )
        
        # Check for required settings
        required_settings = [
            'SECRET_KEY',
            'DATABASES',
            'ALLOWED_HOSTS',
        ]
        
        for setting in required_settings:
            if not hasattr(settings, setting):
                errors.append(
                    Error(
                        f'Missing required setting: {setting}',
                        hint=f'Add {setting} to Django settings',
                        id='solar_data.E101'
                    )
                )
        
        # Check for recommended settings
        recommended_settings = {
            'CORS_ALLOW_ALL_ORIGINS': 'Configure CORS for API access',
            'REST_FRAMEWORK': 'Configure REST framework settings',
            'CACHES': 'Configure cache for better performance',
        }
        
        for setting, hint in recommended_settings.items():
            if not hasattr(settings, setting):
                errors.append(
                    Info(
                        f'Recommended setting not configured: {setting}',
                        hint=hint,
                        id='solar_data.I102'
                    )
                )
        
        # Check static files configuration
        if not hasattr(settings, 'STATIC_URL'):
            errors.append(
                Warning(
                    'STATIC_URL not configured',
                    hint='Configure static files for admin interface',
                    id='solar_data.W102'
                )
            )
        
        # Check media files configuration
        if not hasattr(settings, 'MEDIA_URL'):
            errors.append(
                Info(
                    'MEDIA_URL not configured',
                    hint='Configure media files if you need file uploads',
                    id='solar_data.I103'
                )
            )
        
        # Check timezone configuration
        if not hasattr(settings, 'TIME_ZONE') or settings.TIME_ZONE != 'Africa/Cairo':
            errors.append(
                Warning(
                    f'Timezone set to {getattr(settings, "TIME_ZONE", "not set")}, recommended: Africa/Cairo',
                    hint='Set TIME_ZONE = "Africa/Cairo" for Egyptian solar data',
                    id='solar_data.W103'
                )
            )
        
        # Check for debug mode in production
        if hasattr(settings, 'DEBUG') and settings.DEBUG:
            errors.append(
                Warning(
                    'DEBUG mode is enabled',
                    hint='Set DEBUG = False in production for security',
                    id='solar_data.W104'
                )
            )
        
    except Exception as e:
        errors.append(
            Error(
                f'Error during model configuration check: {str(e)}',
                hint='Check model definitions and Django settings',
                id='solar_data.E199'
            )
        )
    
    return errors


@register()
def check_application_dependencies(app_configs, **kwargs):
    """
    Check application dependencies and requirements
    """
    errors = []
    
    try:
        # Check for required Python packages
        required_packages = [
            'django',
            'djangorestframework',
            'django-filter',
            # 'drf-yasg',  # removed — incompatible with Python 3.12 Nix venv
            'psycopg2-binary',  # PostgreSQL
            'django-cors-headers',
            'python-dateutil',
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            errors.append(
                Error(
                    f'Missing required packages: {", ".join(missing_packages)}',
                    hint='Install missing packages: pip install ' + ' '.join(missing_packages),
                    id='solar_data.E201'
                )
            )
        
        # Check for optional but recommended packages
        recommended_packages = [
            'django-debug-toolbar',
            'django-extensions',
            'gunicorn',
            'whitenoise',
            'redis',
            'django-redis',
        ]
        
        missing_recommended = []
        for package in recommended_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_recommended.append(package)
        
        if missing_recommended:
            errors.append(
                Info(
                    f'Recommended packages not installed: {", ".join(missing_recommended)}',
                    hint='Consider installing these packages for enhanced functionality',
                    id='solar_data.I201'
                )
            )
        
        # Check Django version
        import django
        django_version = django.get_version()
        if django_version < '4.0':
            errors.append(
                Warning(
                    f'Using Django {django_version}, consider upgrading to 4.0+',
                    hint='Upgrade Django for better performance and security',
                    id='solar_data.W201'
                )
            )
        
        # Check Python version
        import sys
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            errors.append(
                Warning(
                    f'Using Python {python_version.major}.{python_version.minor}, recommended: 3.8+',
                    hint='Upgrade Python for better performance and security',
                    id='solar_data.W202'
                )
            )
        
        # Check database backend
        if hasattr(settings, 'DATABASES') and 'default' in settings.DATABASES:
            db_engine = settings.DATABASES['default'].get('ENGINE', '')
            if 'sqlite' in db_engine:
                errors.append(
                    Warning(
                        'Using SQLite database, not recommended for production',
                        hint='Switch to PostgreSQL for better performance and scalability',
                        id='solar_data.W203'
                    )
                )
        
    except Exception as e:
        errors.append(
            Error(
                f'Error during dependency check: {str(e)}',
                hint='Check Python environment and package installations',
                id='solar_data.E299'
            )
        )
    
    return errors


@register()
def check_security_settings(app_configs, **kwargs):
    """
    Check security-related settings
    """
    errors = []
    
    try:
        # Check for insecure secret key
        if hasattr(settings, 'SECRET_KEY'):
            secret_key = settings.SECRET_KEY
            if len(secret_key) < 50:
                errors.append(
                    Error(
                        'Secret key is too short',
                        hint='Generate a longer secret key (min 50 characters)',
                        id='solar_data.E301'
                    )
                )
            if secret_key == 'django-insecure-':
                errors.append(
                    Error(
                        'Using default insecure secret key',
                        hint='Generate a unique secret key for production',
                        id='solar_data.E302'
                    )
                )
        
        # Check for allowed hosts
        if hasattr(settings, 'ALLOWED_HOSTS'):
            if not settings.ALLOWED_HOSTS:
                errors.append(
                    Error(
                        'ALLOWED_HOSTS is empty',
                        hint='Configure ALLOWED_HOSTS for security',
                        id='solar_data.E303'
                    )
                )
            elif '*' in settings.ALLOWED_HOSTS and not settings.DEBUG:
                errors.append(
                    Warning(
                        'ALLOWED_HOSTS contains "*" (wildcard) in production',
                        hint='Specify exact hostnames for better security',
                        id='solar_data.W301'
                    )
                )
        
        # Check for HTTPS/SSL settings
        if not settings.DEBUG:
            if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
                errors.append(
                    Warning(
                        'SSL redirect not enabled',
                        hint='Set SECURE_SSL_REDIRECT = True for production',
                        id='solar_data.W302'
                    )
                )
            
            if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
                errors.append(
                    Warning(
                        'Session cookies not secure',
                        hint='Set SESSION_COOKIE_SECURE = True for production',
                        id='solar_data.W303'
                    )
                )
            
            if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
                errors.append(
                    Warning(
                        'CSRF cookies not secure',
                        hint='Set CSRF_COOKIE_SECURE = True for production',
                        id='solar_data.W304'
                    )
                )
        
        # Check for CORS settings
        if hasattr(settings, 'CORS_ALLOW_ALL_ORIGINS'):
            if settings.CORS_ALLOW_ALL_ORIGINS and not settings.DEBUG:
                errors.append(
                    Warning(
                        'CORS allows all origins in production',
                        hint='Configure specific CORS origins for security',
                        id='solar_data.W305'
                    )
                )
        
        # Check for XSS protection
        if not getattr(settings, 'SECURE_BROWSER_XSS_FILTER', True):
            errors.append(
                Warning(
                    'XSS filter not enabled',
                    hint='Set SECURE_BROWSER_XSS_FILTER = True',
                    id='solar_data.W306'
                )
            )
        
        # Check for content type nosniff
        if not getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', True):
            errors.append(
                Warning(
                    'Content type nosniff not enabled',
                    hint='Set SECURE_CONTENT_TYPE_NOSNIFF = True',
                    id='solar_data.W307'
                )
            )
        
    except Exception as e:
        errors.append(
            Error(
                f'Error during security check: {str(e)}',
                hint='Review security settings configuration',
                id='solar_data.E399'
            )
        )
    
    return errors