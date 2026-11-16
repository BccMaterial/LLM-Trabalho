# Instruções para agentes

## Build, test e lint

Use Poetry a partir da raiz e priorize os comandos do `task`:

```bash
poetry install
poetry run task dev:api
poetry run task dev:agent
poetry run task test
poetry run task lint:check
poetry run task lint:fix
```

Para executar um teste específico:

```bash
poetry run pytest tests/integration/api/appointment/test_appointment_post.py -q
poetry run pytest tests/integration/api/appointment/test_appointment_post.py::test_create_appointment_defaults_to_pending -q
```

Configure as variáveis de `.env.example`; a API exige `DATABASE_URL` e o
agente exige `LLM_BASE_URL` e `OPENAI_API_KEY` (`LLM_MODEL` é opcional).
API e PostgreSQL podem ser iniciados com:

```bash
docker compose --env-file .env -f infra/compose.yaml up --build
```

## Arquitetura do código

`src/api/app.py` cria a aplicação Flask, registra as blueprints e injeta as
dependências de banco e migrations em `app.extensions`. Controllers em
`src/api/controllers` tratam HTTP e validação de entrada; services em
`src/api/services` concentram operações e regras; views em `src/api/views`
formatam JSON; models em `src/api/models` definem o domínio SQLAlchemy.

O middleware em `src/api/middlewares` autentica requisições com sessão em
cookie `HttpOnly` ou Bearer token administrativo. Policies em
`src/api/policies` mantêm as decisões de autorização por role separadas do
middleware e dos services. Migrations Alembic ficam em
`infra/alembic/versions`, usam `Base.metadata` de
`src/api/models/__init__.py` e precisam de `upgrade()` e `downgrade()`.

`src/agent` é um protótipo separado de conectividade com LLM, ainda não
integrado à API ou a um fluxo conversacional. O desenho-alvo descrito em
`docs/arquitetura.md` e o contrato em `docs/io.md` não significam que agenda,
pacientes e os três agentes já estejam implementados; registros mutáveis de
pacientes devem vir da API, não do RAG proposto.

## Convenções

- Mantenha rotas nas blueprints, formatação JSON nas views, operações
  reutilizáveis nos services e autorização nas policies. Compartilhe
  dependências por `app.extensions`.
- Testes unitários seguem os caminhos de `src`. Testes de integração são
  divididos por método (`test_*_get.py`, `test_*_post.py`, etc.) e por acesso
  em `access/`, com um arquivo por role testada. Cubra caminhos felizes e
  tristes, incluindo autenticação, autorização, validação e conflitos.
- Os testes usam imports `api.*`, pois `src` está no `pythonpath`; fixtures
  podem injetar banco SQLite e token via `create_app`.
- Respostas para pacientes seguem `docs/io.md`: português, `fonte`,
  `suficiencia`, clarificação de entradas incompletas/ambíguas e nenhuma
  invenção clínica ou de política. Não exponha segredos nem conteúdo clínico
  em logs; agendamento exige confirmação explícita.
- PRs devem ser abertos em português com resumo do trabalho. Commits seguem
  Conventional Commits e são escritos em inglês.
