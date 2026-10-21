#!/bin/sh
# Crea el usuario y la base de datos de n8n. Lo ejecuta PostgreSQL UNA sola vez, al crear el volumen
# de datos por primera vez (si el volumen ya existe, no se vuelve a ejecutar).
# La contraseña llega como variable de psql (:'clave'), así que puede contener cualquier carácter.
set -eu

psql -v ON_ERROR_STOP=1 -v clave="$N8N_DB_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE n8n LOGIN PASSWORD :'clave';
CREATE DATABASE n8n OWNER n8n;
SQL
