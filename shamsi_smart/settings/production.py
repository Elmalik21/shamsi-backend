"""
Shamsi Smart — Production Settings (Railway)
Fixed: no decouple, no drf_yasg, pure os.environ
"""
import os
import sys
import urllib.parse
from pathlib import Path

print("[production.py] Loading started", file=sys.stderr)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-shamsi-fallback'))
DEBUG = False

ALLOWED_HOSTS = ['shamsi-backend-production.up.railway.app', '.railway.app', 'localhost', '127.0.0.1', '*']

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'rest_framework.authtoken', 'corsheaders', 'django_filters',
    'solar_data', 'api', 'dashboard', 'ai_engine',
]

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
WSGI_APPLICATION = 'shamsi_smart.wsgi.application'

TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.debug', 'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]

_db_url = os.environ.get('DATABASE_URL', '')
print(f"[production.py] DATABASE_URL present={bool(_db_url)}", file=sys.stderr)
if _db_url:
    _u = urllib.parse.urlparse(_db_url)
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': _u.path.lstrip('/'), 'USER': _u.username or '', 'PASSWORD': _u.password or '', 'HOST': _u.hostname or '', 'PORT': str(_u.port or 5432), 'CONN_MAX_AGE': 600, 'OPTIONS': {'sslmode': 'require'}}}
    print(f"[production.py] DB host={_u.hostname}", file=sys.stderr)
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
    print("[production.py] WARNING: no DATABASE_URL, using SQLite", file=sys.stderr)

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'], 'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication', 'rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 50, 'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend']}

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = ['https://shamsiai.netlify.app', 'http://localhost:5173', 'http://localhost:3000']
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = ['accept', 'accept-encoding', 'authorization', 'content-type', 'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with']

CSRF_TRUSTED_ORIGINS = ['https://shamsiai.netlify.app', 'https://shamsi-backend-production.up.railway.app', 'https://*.railway.app']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

LOGGING = {'version': 1, 'disable_existing_loggers': False, 'handlers': {'console': {'class': 'logging.StreamHandler'}}, 'loggers': {'django': {'handlers': ['console'], 'level': 'INFO'}}}
SOLAR_DATA_YEARS = list(range(2018, 2027))

# Dashboard auth
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
for _p in ['media', 'staticfiles']:
    os.makedirs(BASE_DIR / _p, exist_ok=True)

# --- AI / ML capability flags (Railway-safe lazy checks) ---
# Probed at startup so views can guard against OOM or missing deps gracefully.
AI_MODELS_DIR = BASE_DIR / 'ai_engine' / 'models'

TORCH_AVAILABLE = False
try:
    import torch as _torch  # noqa: F401
    TORCH_AVAILABLE = True
    print("[production.py] torch available ✅", file=sys.stderr)
except (ImportError, Exception) as _e:
    print(f"[production.py] torch NOT available ({_e}) — roof/CNN analysis disabled", file=sys.stderr)

SKLEARN_AVAILABLE = False
try:
    import sklearn as _sklearn  # noqa: F401
    SKLEARN_AVAILABLE = True
    print("[production.py] scikit-learn available ✅", file=sys.stderr)
except ImportError as _e:
    print(f"[production.py] scikit-learn NOT available ({_e}) — ML models will use physics fallback", file=sys.stderr)