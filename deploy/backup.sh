#!/usr/bin/env bash
# Copia de seguridad de las dos bases de datos (TaskFlow y n8n) en archivos comprimidos.
#
#   ./backup.sh                      copia en ./backups y borra las de más de 14 días
#   BACKUP_DIR=/mnt/copias BACKUP_DAYS=30 ./backup.sh
#
# Programarla cada noche (crontab -e):
#   0 3 * * * /opt/taskflow/deploy/backup.sh >> /var/log/taskflow-backup.log 2>&1
#
# IMPORTANTE: las copias quedan EN EL MISMO SERVIDOR. Si el servidor se pierde, se pierden con él.
# Cópialas a otro sitio (otro servidor, almacenamiento de objetos...): ver README.md.
# Además de estas copias, guarda aparte el archivo ".env" (sobre todo N8N_ENCRYPTION_KEY).
set -euo pipefail

cd "$(dirname "$0")"
destino="${BACKUP_DIR:-./backups}"
dias="${BACKUP_DAYS:-14}"
sello="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$destino"
umask 077   # las copias contienen datos: solo las lee quien las creó

for base in taskflow n8n; do
    archivo="$destino/${base}-${sello}.sql.gz"
    # Se escribe en un archivo temporal y solo se renombra si todo salió bien: así nunca queda
    # una copia a medias con aspecto de válida.
    docker compose exec -T postgres pg_dump -U taskflow --clean --if-exists --no-owner "$base" \
        | gzip -9 > "$archivo.tmp"
    gzip -t "$archivo.tmp"
    if ! gzip -dc "$archivo.tmp" | head -n 20 | grep -q "PostgreSQL database dump"; then
        rm -f "$archivo.tmp"
        echo "ERROR: la copia de '$base' no parece un volcado de PostgreSQL" >&2
        exit 1
    fi
    mv "$archivo.tmp" "$archivo"
    echo "OK  $archivo ($(du -h "$archivo" | cut -f1))"
done

# Retención: se borran solo las copias antiguas con el formato de este script.
find "$destino" -maxdepth 1 -name '*-????????T??????Z.sql.gz' -mtime +"$dias" -print -delete
