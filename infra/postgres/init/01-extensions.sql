-- Runs only the first time the data volume is created.
-- From F2 on, schema changes, including extensions, are managed with Alembic migrations.
CREATE EXTENSION IF NOT EXISTS vector;
