-- Migración: tasks.project (nombre del proyecto en texto libre). PostgreSQL 13+.
-- Para bases creadas antes de que schema.sql incluyera tasks.project; es idempotente.
-- Transitorio: cuando exista la tabla projects se migrará a project_id.
-- Uso: psql -d taskflow -f add_task_project.sql

BEGIN;

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS project VARCHAR(60);

COMMIT;
