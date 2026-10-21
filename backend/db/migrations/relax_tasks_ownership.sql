-- Migración: tasks.project_id y tasks.created_by pasan a ser opcionales. PostgreSQL 13+.
-- Motivo: la aplicación aún no tiene proyectos ni usuarios y no rellena esas columnas, así que
-- con NOT NULL toda inserción de la API fallaba en bases creadas con el schema.sql antiguo.
-- Es idempotente (DROP NOT NULL no falla si la columna ya admite nulos).
-- Cuando existan proyectos y usuarios: rellenar los datos antiguos y volver a poner NOT NULL.
-- Uso: psql -d taskflow -f relax_tasks_ownership.sql

BEGIN;

ALTER TABLE tasks ALTER COLUMN project_id DROP NOT NULL;
ALTER TABLE tasks ALTER COLUMN created_by DROP NOT NULL;

COMMIT;
