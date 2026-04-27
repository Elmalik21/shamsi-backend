"""
Shamsi Smart Project Settings - Refactored for Codespaces
"""
import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'unsafe-development-key-change-in-production')

# التغيير: تفعيل DEBUG لبيئة التطوير لرؤية تفاصيل الأخطاء
DEBUG = True 

# التغيير: السماح لجميع نطاقات Codespaces بالوصول للخادم
ALLOWED_HOSTS = [
    '*',
    '.app.github.dev',
    'localhost',
    '127.0.0.1'
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_yasg',
    
    # Local apps
    'solar_data',   # Main Data App (Source of Truth)
    'api',          # API Logic
    'dashboard',    # Frontend Logic
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', # لا تزال مفعلة للأمان
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

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF Settings
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

# CORS - السماح لجميع المنشآت أثناء التطوير لتجنب مشاكل الربط مع React

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'solar_data': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}

# Ensure directories exist
for path in ['logs', 'media']:
    os.makedirs(BASE_DIR / path, exist_ok=True)

# Solar Data Configuration
SOLAR_DATA_YEARS = list(range(2018, 2027)) 

# --- الأهم لحل مشكلة 403 Forbidden ---
# السماح لجميع النطاقات الخاصة بـ GitHub Codespaces
CSRF_TRUSTED_ORIGINS = [
    "https://*.app.github.dev",
    "https://*.github.dev",
    "https://localhost:8000", # ضروري جداً بناءً على رسالة الخطأ الأخيرة
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# تفعيل خيارات البروكسي لبيئة GitHub
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# في بيئة التطوير فقط، يفضل السماح للـ CORS بالكامل لربط React بسهولة
CORS_ALLOW_ALL_ORIGINS = True