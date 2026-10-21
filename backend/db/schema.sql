-- TaskFlow AI: esquema relacional (PostgreSQL 13+)
-- Uso: psql -d taskflow -f schema.sql

BEGIN;

-- Mantiene updated_at al día en cada UPDATE
CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE users (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Unicidad de email sin distinguir mayúsculas
CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));

CREATE TABLE projects (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id    INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    description TEXT,
    archived    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Transitorio: la aplicación aún no tiene proyectos ni usuarios, así que no los rellena
    -- (ver TaskModel). Cuando existan, se rellenarán los datos antiguos y se volverán NOT NULL.
    project_id     INTEGER      REFERENCES projects (id) ON DELETE CASCADE,
    created_by     INTEGER      REFERENCES users (id),
    assigned_to   INTEGER      REFERENCES users (id) ON DELETE SET NULL,
    parent_task_id INTEGER      REFERENCES tasks (id) ON DELETE CASCADE,
    title          VARCHAR(200) NOT NULL,
    description    TEXT,
    status         VARCHAR(20)  NOT NULL DEFAULT 'todo'
                   CHECK (status IN ('todo', 'in_progress', 'done')),
    priority       SMALLINT     NOT NULL DEFAULT 2
                   CHECK (priority BETWEEN 1 AND 4),
    due_date       DATE,
    completed_at   TIMESTAMPTZ,
    -- id del evento en el calendario externo (Google Calendar)
    external_event_id VARCHAR(255),
    -- cuándo se envió el recordatorio de vencimiento (evita avisos repetidos)
    reminded_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CHECK (parent_task_id IS NULL OR parent_task_id <> id),
    -- una tarea está hecha si y solo si tiene fecha de finalización
    CHECK ((status = 'done') = (completed_at IS NOT NULL))
);

CREATE TABLE labels (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id INTEGER     NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    name       VARCHAR(50) NOT NULL,
    color      CHAR(7)     CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    UNIQUE (project_id, name)
);

CREATE TABLE task_labels (
    task_id  INTEGER NOT NULL REFERENCES tasks (id)  ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES labels (id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, label_id)
);

CREATE TABLE comments (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id    INTEGER     NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    user_id    INTEGER     NOT NULL REFERENCES users (id),
    body       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_suggestions (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    project_id INTEGER     REFERENCES projects (id) ON DELETE SET NULL,
    kind       VARCHAR(30) NOT NULL,
    model      VARCHAR(60),
    prompt     TEXT,
    response   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Registro de ejecuciones de las automatizaciones (n8n)
CREATE TABLE workflow_logs (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workflow     VARCHAR(80)  NOT NULL,
    execution_id VARCHAR(40),
    task_id      INTEGER      REFERENCES tasks (id) ON DELETE SET NULL,
    status       VARCHAR(20)  NOT NULL CHECK (status IN ('success', 'failed')),
    detail       TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Eventos pendientes de enviar a n8n (patrón outbox transaccional). Se guardan en la misma
-- transacción que el cambio que los origina; un despachador los envía en orden y con reintentos.
CREATE TABLE event_outbox (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id        VARCHAR(36)  NOT NULL UNIQUE,   -- clave de idempotencia para n8n
    event           VARCHAR(50)  NOT NULL,
    data            JSONB        NOT NULL,
    occurred_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    status          VARCHAR(10)  NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'dead')),
    attempts        INTEGER      NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    locked_until    TIMESTAMPTZ,                    -- reserva del despachador que lo está enviando
    last_error      TEXT,
    sent_at         TIMESTAMPTZ
);

-- Triggers de updated_at
CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Índices de apoyo a las consultas habituales
CREATE INDEX idx_projects_owner      ON projects (owner_id);
CREATE INDEX idx_tasks_project_state ON tasks (project_id, status);
CREATE INDEX idx_tasks_assignee_due  ON tasks (assigned_to, due_date);
CREATE INDEX idx_tasks_parent        ON tasks (parent_task_id);
CREATE INDEX idx_comments_task       ON comments (task_id, created_at);
CREATE INDEX idx_ai_user_created     ON ai_suggestions (user_id, created_at);

-- Índices sobre claves foráneas sin cubrir (PostgreSQL no los crea solo)
CREATE INDEX idx_tasks_created_by    ON tasks (created_by);
CREATE INDEX idx_comments_user       ON comments (user_id);
CREATE INDEX idx_task_labels_label   ON task_labels (label_id);
CREATE INDEX idx_ai_project          ON ai_suggestions (project_id);
CREATE INDEX idx_workflow_logs_task  ON workflow_logs (task_id);
CREATE INDEX idx_outbox_pending      ON event_outbox (id) WHERE status = 'pending';
CREATE INDEX idx_tasks_due_pending   ON tasks (due_date) WHERE status <> 'done';

COMMIT;
