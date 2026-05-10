"""
Shamsi Smart Project Settings - Optimized for Railway & Production
"""
import os
import sys
from pathlib import Path

print("[settings.py] Loading started", file=sys.stderr)

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security ---
SECRET_KEY = os.environ.get('SECRET_KEY', os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-prod-key-77-shamsi-smart'))
DEBUG = os.environ.get('DEBUG', os.environ.get('DJANGO_DEBUG', 'False')).lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [
    'shamsi-backend-production.up.railway.app',
    '.railway.app',
    'localhost',
    '127.0.0.1',
    '*',
]

# --- Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # django.contrib.gis REMOVED — requires PostGIS on Railway Postgres
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    # drf_yasg removed — pkg_resources unavailable in Python 3.12 Nix venv
    'solar_data',
    'api',
    'dashboard',
]

# --- Middleware (CorsMiddleware MUST be first) ---
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

# --- Database ---
# Parse DATABASE_URL manually — avoids dj_database_url edge cases on Railway
import urllib.parse as _urlparse
import sys as _sys

_DATABASE_URL = os.environ.get('DATABASE_URL', '')
print(f"[settings] DATABASE_URL present: {bool(_DATABASE_URL)}", file=_sys.stderr)

if _DATABASE_URL:
    _u = _urlparse.urlparse(_DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _u.path.lstrip('/'),
            'USER': _u.username,
            'PASSWORD': _u.password,
            'HOST': _u.hostname,
            'PORT': str(_u.port or 5432),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {'sslmode': 'require'} if not DEBUG else {},
        }
    }
else:
    print("[settings] WARNING: DATABASE_URL not set, using SQLite", file=_sys.stderr)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# --- Static files ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- i18n ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- REST Framework ---
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# --- CORS (PRIORITY 1 FIX) ---
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    'https://shamsiai.netlify.app',
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# --- CSRF ---
CSRF_TRUSTED_ORIGINS = [
    'https://shamsiai.netlify.app',
    'https://shamsi-backend-production.up.railway.app',
    'https://*.railway.app',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# --- Logging ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'django': {'handlers': ['console'], 'level': 'INFO'}},
}

for _p in ['media', 'staticfiles']:
    os.makedirs(BASE_DIR / _p, exist_ok=True)

SOLAR_DATA_YEARS = list(range(2018, 2027))
