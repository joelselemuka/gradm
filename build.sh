#!/usr/bin/env bash
# =============================================================================
# Script de build Render — exécuté automatiquement à chaque déploiement.
# =============================================================================
set -euo pipefail

echo "==> Installation des dépendances..."
pip install -r requirements/base.txt

echo "==> Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

echo "==> Application des migrations..."
python manage.py migrate --noinput

echo "==> Analyse des alertes d'expiration..."
python manage.py scan_expiration_alerts || true

echo "==> Build terminé avec succès."
