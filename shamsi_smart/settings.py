"""
Shamsi Smart Project Settings - Optimized for Railway & Production
"""
import os
import dj_database_url
from pathlib import Path
from datetime import timedelta
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# تأكد من أن هذا المسار يشير إلى المجلد الرئيسي للمشروع (المكان الذي يوجد به manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent 

# --- Security Settings ---
SECRET_KEY = config('SECRET_KEY', default='django-insecure-prod-key-77-shamsi-smart')
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = [
    'shamsi-backend-production.up.railway.app', 
    '.railway.app',                             
    'localhost',
    '127.0.0.1',
    '*',                                        
]

# --- Application definition ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis', 
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_yasg',
    
    # Local apps
    'solar_data',
    'api',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'shamsi_smart.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'shamsi_smart.wsgi.application'

# --- Database Configuration ---
# التعديل الجوهري: محاولة قراءة DATABASE_URL من البيئة (Railway) أولاً، ثم من ملف .env
db_url = os.environ.get('DATABASE_URL') or config('DATABASE_URL', default=None)

if db_url:
    DATABASES = {
        'default': dj_database_url.parse(db_url)
    }
    DATABASES['default']['CONN_MAX_AGE'] = 600
    # تفعيل SSL فقط إذا كان الاتصال بـ Postgres أونلاين
    if db_url.startswith('postgres'):
        DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
else:
    # خيار احتياطي في حالة عدم وجود أي إعدادات (يفضل تجنبه)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# --- Static & Media Files ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- REST Framework Settings ---
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# --- CORS & CSRF Settings ---
CORS_ALLOW_ALL_ORIGINS = True 
CSRF_TRUSTED_ORIGINS = [
    "https://shamsi-backend-production.up.railway.app",
    "https://*.railway.app",
    "http://localhost:8000",
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# --- Logging ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
    },
}

# التأكد من وجود المجلدات اللازمة
for path in ['media', 'staticfiles']:
    os.makedirs(BASE_DIR / path, exist_ok=True)

SOLAR_DATA_YEARS = list(range(2018, 2027))
