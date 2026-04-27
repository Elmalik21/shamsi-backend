"""
Shamsi Smart — Local Development Settings
SQLite, DEBUG=True, all CORS allowed.
"""
from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = [
    '*',
    '.app.github.dev',
    'localhost',
    '127.0.0.1',
]

# SQLite for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Allow all CORS origins during development
CORS_ALLOW_ALL_ORIGINS = True

# Relaxed CSRF for Codespaces / local dev
CSRF_TRUSTED_ORIGINS = [
    'https://*.app.github.dev',
    'https://*.github.dev',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# No SSL enforcement locally
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Console logging only
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django':     {'handlers': ['console'], 'level': 'INFO'},
        'solar_data': {'handlers': ['console'], 'level': 'DEBUG'},
        'ai_engine':  {'handlers': ['console'], 'level': 'DEBUG'},
    },
}
