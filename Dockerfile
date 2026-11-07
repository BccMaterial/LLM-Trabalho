FROM python:3.14-slim

ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY src ./src
COPY infra/alembic ./infra/alembic

EXPOSE 5000

CMD ["python", "-m", "src.api.app"]
