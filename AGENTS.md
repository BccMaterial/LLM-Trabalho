# Copilot instructions

## Build, test, and lint

Use Poetry from the repository root:

```bash
poetry install
poetry run task dev:api
poetry run task dev:agent
poetry run task test
poetry run pytest tests/integration/api/test_example.py -q
poetry run pytest tests/integration/api/test_example.py::test_when_name_is_passed -q
poetry run task lint:check
poetry run task lint:fix
```

The API requires `DATABASE_URL`; the agent uses `LLM_BASE_URL` and
`OPENAI_API_KEY` (and optionally `LLM_MODEL`). Use `.env.example` for the
environment-variable names. The API and PostgreSQL can also be started with
`docker compose --env-file .env -f infra/compose.yaml up --build`.

## Architecture

- `src/api/app.py` creates the Flask app, configures the SQLAlchemy connector
  and migration service, and registers API blueprints. Controllers define
  routes, delegate response formatting to views, and use services for
  application/database operations.
- `DatabaseConnector` provides transaction-scoped SQLAlchemy sessions. Schema
  migrations are managed by Alembic under `infra/alembic`; the migration API
  lists and applies pending revisions and requires a configured bearer token.
- `src/agent/app.py` is currently a separate LLM connectivity prototype. It
  sends a fixed test message through the OpenAI-compatible client configured
  by environment variables; it is not yet integrated with the Flask API or a
  conversational workflow.
- The intended patient-facing system and its input/output contract are
  documented in `README.md`, `docs/arquitetura.md`, and `docs/io.md`. The RAG
  architecture in `docs/rag.md` is a proposal, not an implemented index or API.
  Keep patient-specific, changing records sourced from the clinic API rather
  than treating proposed document retrieval as a source for them.

## Repository conventions

- Keep API route handling in blueprints under `src/api/controllers`, JSON
  response construction in `src/api/views`, and reusable operations in
  `src/api/services`. Register shared app dependencies through Flask
  `app.extensions`; tests can inject a database URL and migration token through
  `create_app`.
- Tests live under `tests/` and use pytest. API integration tests use Flask's
  test client and SQLite (including temporary file databases for migration
  tests), so they do not require a running PostgreSQL service.
- Add Alembic revisions in `infra/alembic/versions` with both `upgrade()` and
  `downgrade()` operations. Alembic uses `Base.metadata` from
  `src/api/models/__init__.py`.
- Format Python with Black and isort using the Poetry tasks above. Test imports
  resolve `src` as the Python path, so API tests import modules as `api.*`.
- Patient-facing behavior is scoped to neuropsychological assessment
  scheduling and related clinic guidance. Follow the documented I/O contract:
  responses identify their supporting source and state whether it was
  sufficient; ask for missing or ambiguous information, and do not invent
  clinical or policy facts. Keep responses in Portuguese where they address
  patients.
