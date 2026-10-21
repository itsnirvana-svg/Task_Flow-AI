#!/usr/bin/env bash
# Restaura una copia de seguridad SUSTITUYENDO los datos actuales de esa base de datos.
#
#   ./restore.sh taskflow backups/taskflow-20261021T030000Z.sql.gz
#   ./restore.sh n8n      backups/n8n-20261021T030000Z.sql.gz
#
# Antes de restaurar, el servicio que usa esa base se detiene (para que no escriba mientras tanto) y
# se pide confirmar escribiendo el nombre de la base. Al terminar se vuelve a arrancar.
# Prueba este procedimiento ANTES de necesitarlo: una copia que nunca se ha restaurado no es una copia.
set -euo pipefail

cd "$(dirname "$0")"

if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <taskflow|n8n> <archivo.sql.gz>" >&2
    exit 2
fi
base="$1"
archivo="$2"

case "$base" in
    taskflow) servicio="api" ;;
    n8n) servicio="n8n" ;;
    *) echo "La base debe ser 'taskflow' o 'n8n'." >&2; exit 2 ;;
esac
[ -f "$archivo" ] || { echo "No existe el archivo: $archivo" >&2; exit 2; }
gzip -t "$archivo" || { echo "El archivo está dañado: $archivo" >&2; exit 2; }

echo "Se va a SUSTITUIR el contenido actual de la base '$base' con: $archivo"
read -r -p "Para confirmar, escribe el nombre de la base ($base): " respuesta
[ "$respuesta" = "$base" ] || { echo "Cancelado."; exit 1; }

docker compose stop "$servicio"
gzip -dc "$archivo" | docker compose exec -T postgres \
    psql -U taskflow -d "$base" -v ON_ERROR_STOP=1 --quiet
docker compose start "$servicio"
echo "Restauración de '$base' terminada."
