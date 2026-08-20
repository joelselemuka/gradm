#!/usr/bin/env bash
set -e

echo "==> Application des migrations..."
python manage.py migrate --noinput

echo "==> Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

echo "==> Initialisation du compte administrateur..."
python manage.py init_admin

echo "==> Verification des alertes d'expiration..."
python manage.py scan_expiration_alerts || true

PORT_NUM="${PORT:-10000}"
echo "==> Demarrage du serveur Daphne sur le port ${PORT_NUM}..."
exec daphne -b 0.0.0.0 -p "${PORT_NUM}" config.asgi:application