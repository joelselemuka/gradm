from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
# En production, définir DJANGO_DEBUG=false explicitement.
# La valeur par défaut est intentionnellement false pour éviter toute
# exposition accidentelle des tracebacks Django.
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
_allowed = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host]
# Sur Render, le domaine *.onrender.com est ajouté automatiquement.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    _allowed.append(RENDER_EXTERNAL_HOSTNAME)
ALLOWED_HOSTS = _allowed

# CSRF : Django 4+ exige que les origines soient explicitement autorisées
# derrière un reverse proxy. Accepte une liste séparée par des virgules.
_csrf_origins = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
if RENDER_EXTERNAL_HOSTNAME:
    _csrf_origins.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
CSRF_TRUSTED_ORIGINS = _csrf_origins

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "django_ratelimit",
    "channels",
    "django_celery_beat",
    "apps.core",
    "apps.accounts",
    "apps.products",
    "apps.inventory",
    "apps.sales",
    "apps.pos",
    "apps.audit",
    "apps.suppliers",
    "apps.purchases",
    "apps.expenses",
    "apps.customers",
    "apps.reports",
    "apps.promotions",
    "apps.notifications",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise doit être juste après SecurityMiddleware pour servir
    # les fichiers statiques sans passer par Django (requis sur Render).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.pos.middleware.OpenCashSessionRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "builtins": ["apps.core.templatetags.formatting"],
        "context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.core.context_processors.navigation",
        ],
    },
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Base de données : priorité à DATABASE_URL (Render, Heroku, etc.)
# sinon construction depuis les variables individuelles.
_database_url = os.getenv("DATABASE_URL")
_postgres_db  = os.getenv("POSTGRES_DB")

if _database_url:
    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}
elif _postgres_db:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _postgres_db,
        "USER": os.getenv("POSTGRES_USER", "supermarket"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "supermarket"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "OPTIONS": {"connect_timeout": 10},
    }}
elif not DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "DATABASE_URL ou POSTGRES_DB doit être défini en production."
    )
else:
    # Fallback SQLite uniquement autorisé en développement local (DEBUG=True).
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
LANGUAGE_CODE = "fr"
TIME_ZONE = os.getenv("TIME_ZONE", "Africa/Johannesburg")
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Configuration WhiteNoise pour servir les fichiers statiques (CSS, JS, images)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"

REDIS_URL = os.getenv("REDIS_URL", "")

# Cache : Redis si disponible, sinon LocMemCache (demo sans Redis)
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# Channel Layers : Redis si disponible, sinon InMemory (WebSockets locaux uniquement)
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# Celery : Redis si disponible, sinon execution synchrone (taches dans le meme process)
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CELERY_TASK_ALWAYS_EAGER = True   # Les taches Celery s'executent en synchrone
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"

CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {"daily-sales-report": {"task": "apps.reports.tasks.send_daily_sales_report", "schedule": 86400}, "expiry-alerts": {"task": "apps.inventory.tasks.notify_expiring_lots", "schedule": 86400}}
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
ADMIN_REPORT_EMAIL = os.getenv("ADMIN_REPORT_EMAIL", "")

# Durée de vie des sessions : 8 heures (au lieu de 14 jours par défaut Django).
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "28800"))

# Headers de sécurité présents en toutes circonstances.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# TLS est imposé uniquement hors développement. Le reverse proxy (Nginx) doit
# transmettre le schéma original via X-Forwarded-Proto.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Logging structuré vers la console (capturé par Docker/systemd en production).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
