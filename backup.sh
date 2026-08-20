#!/bin/bash
# =============================================================================
# Script de sauvegarde PostgreSQL — Application GSM
# =============================================================================
# Usage : ./backup.sh
# Recommandation : planifier via cron (toutes les heures)
#   0 * * * * /opt/gsm/backup.sh >> /var/log/gsm-backup.log 2>&1
#
# Prérequis :
#   - Docker en cours d'exécution
#   - Variables d'environnement chargées (ou les renseigner ci-dessous)
#   - Répertoire BACKUP_DIR accessible en écriture
# =============================================================================

set -euo pipefail

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #
BACKUP_DIR="${BACKUP_DIR:-/opt/gsm/backups}"
CONTAINER="${DB_CONTAINER:-gsm-db-1}"
DB_NAME="${POSTGRES_DB:-supermarket}"
DB_USER="${POSTGRES_USER:-supermarket}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/gsm_${DATE}.sql.gz"

# --------------------------------------------------------------------------- #
# Création du répertoire de sauvegarde                                         #
# --------------------------------------------------------------------------- #
mkdir -p "${BACKUP_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Démarrage de la sauvegarde GSM..."

# --------------------------------------------------------------------------- #
# Dump PostgreSQL compressé                                                    #
# --------------------------------------------------------------------------- #
if docker exec "${CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"; then
    SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sauvegarde créée : ${BACKUP_FILE} (${SIZE})"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERREUR : La sauvegarde a échoué !" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# --------------------------------------------------------------------------- #
# Nettoyage des sauvegardes anciennes                                          #
# --------------------------------------------------------------------------- #
DELETED=$(find "${BACKUP_DIR}" -name "gsm_*.sql.gz" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supprimé ${DELETED} sauvegarde(s) de plus de ${RETENTION_DAYS} jours."
fi

# --------------------------------------------------------------------------- #
# Optionnel : envoi vers stockage externe (S3, Backblaze, etc.)               #
# Décommenter et configurer selon votre fournisseur de stockage.              #
# --------------------------------------------------------------------------- #
# if command -v aws &> /dev/null; then
#     aws s3 cp "${BACKUP_FILE}" "s3://mon-bucket-gsm/backups/$(basename ${BACKUP_FILE})"
#     echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sauvegarde envoyée vers S3."
# fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sauvegarde terminée avec succès."
