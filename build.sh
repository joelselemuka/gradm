#!/usr/bin/env bash
set -euo pipefail

echo "==> Installation des dependances..."
pip install -r requirements/base.txt

echo "==> Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

echo "==> Application des migrations..."
python manage.py migrate --noinput

echo "==> Initialisation du compte administrateur..."
python manage.py init_admin

echo "==> Analyse des alertes d'expiration..."
python manage.py scan_expiration_alerts || true

echo "==> Build termine avec succes."