# Settings de test : hérite de la config principale en overridant
# uniquement les composants qui nécessitent des services externes (Redis).
from config.settings import *  # noqa: F401, F403

# Remplace le Redis Channel Layer par une version en mémoire pour les tests.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Utilise LocMemCache en tests (pas de Redis local requis).
# Le check E003 est silencé car le rate limiting est désactivé en tests.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
RATELIMIT_ENABLE = False
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]
