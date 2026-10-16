-- Migración: tabla de eventos pendientes hacia n8n (outbox transaccional). PostgreSQL 13+.
-- Para bases creadas antes de que schema.sql incluyera event_outbox; es idempotente.
-- Uso: psql -d taskflow -f add_event_outbox.sql

BEGIN;

CREATE TABLE IF NOT EXISTS event_outbox (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id        VARCHAR(36)  NOT NULL UNIQUE,
    event           VARCHAR(50)  NOT NULL,
    data            JSONB        NOT NULL,
    occurred_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    status          VARCHAR(10)  NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'dead')),
    attempts        INTEGER      NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_error      TEXT,
    sent_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending ON event_outbox (id) WHERE status = 'pending';

COMMIT;
