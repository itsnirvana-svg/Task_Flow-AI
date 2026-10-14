-- Migración: integración con Google Calendar (PostgreSQL 13+)
-- Para bases creadas con una versión anterior de schema.sql. Las instalaciones nuevas ya
-- incluyen tasks.external_event_id en schema.sql; por eso es idempotente (IF NOT EXISTS).
-- Requiere users, tasks y set_updated_at().
-- Uso: psql -d taskflow -f add_calendar_integrations.sql

BEGIN;

CREATE TABLE IF NOT EXISTS calendar_integrations (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    provider          VARCHAR(20)  NOT NULL DEFAULT 'google'
                      CHECK (provider IN ('google')),
    calendar_id       VARCHAR(255) NOT NULL DEFAULT 'primary',
    -- refresh token CIFRADO en la aplicación; nunca en texto plano
    refresh_token_enc TEXT         NOT NULL,
    scopes            TEXT,
    connected_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
);

DROP TRIGGER IF EXISTS trg_calendar_integrations_updated_at ON calendar_integrations;
CREATE TRIGGER trg_calendar_integrations_updated_at BEFORE UPDATE ON calendar_integrations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS external_event_id VARCHAR(255);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS reminded_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_tasks_external_event ON tasks (external_event_id)
    WHERE external_event_id IS NOT NULL;

COMMIT;
