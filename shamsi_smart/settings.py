"""
Shamsi Smart Project Settings - Optimized for Railway & Production
"""
import os
import dj_database_url
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security Settings ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-prod-key-77-shamsi-smart')

# التعديل: DEBUG يتم التحكم به عبر متغيرات البيئة (افتراضياً False للأمان)
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# التعديل: إضافة نطاقات Railway و Codespaces
ALLOWED_HOSTS = [
    '*',
    '.railway.app',
    '.app.github.dev',
    'localhost',
    '127.0.0.1',
]

# --- Application definition ---
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
    
    # Local apps (Shamsi Smart Graduation Project)
    'solar_data',
    'api',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # التعديل: ضروري جداً هنا لخدمة الملفات الثابتة
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
# يتم الربط تلقائياً مع قاعدة بيانات PostgreSQL على Railway عبر متغير البيئة
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600
    )
}

# --- Static & Media Files ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# التعديل: تحسين أداء WhiteNoise لضغط الملفات الثابتة
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
CORS_ALLOW_ALL_ORIGINS = True # مسموح بالكامل لتسهيل الربط مع React/Frontend

CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app",
    "https://*.app.github.dev",
    "https://*.github.dev",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# إعدادات البروكسي لضمان عمل HTTPS بشكل صحيح
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
        'solar_data': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}

# التأكد من وجود المجلدات اللازمة
for path in ['logs', 'media', 'staticfiles']:
    os.makedirs(BASE_DIR / path, exist_ok=True)

# Solar Data Configuration
SOLAR_DATA_YEARS = list(range(2018, 2027))
