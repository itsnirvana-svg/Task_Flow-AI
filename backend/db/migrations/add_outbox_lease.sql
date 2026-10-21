-- Migración: reserva de eventos del outbox (varios despachadores sin duplicados). PostgreSQL 13+.
-- Para bases creadas antes de que event_outbox tuviera locked_until; es idempotente.
-- Uso: psql -d taskflow -f add_outbox_lease.sql

BEGIN;

ALTER TABLE event_outbox ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;

COMMIT;
