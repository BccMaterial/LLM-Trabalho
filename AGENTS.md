# Instruções para agentes

## Fluxo de trabalho

- Após **toda** alteração de código, execute `poetry run task lint:fix` na raiz (`isort . && black .`). Não fique no ciclo check/fix: `poetry run task lint:check` apenas ao preparar o relatório do PR.
- Commits em inglês no padrão Conventional Commits; PRs em português com resumo do trabalho.

## Comandos (Poetry na raiz)

```bash
poetry install
poetry run task dev            # sobe PostgreSQL + API (Docker) e aplica migrations
poetry run task dev:api        # python -m src.api.app
poetry run task dev:agent      # python -m src.agent.app: popula dados sintéticos e abre a CLI (exige API no ar)
poetry run task migrations:up  # aplica migrations via POST /api/migrations
poetry run task test
poetry run pytest tests/integration/api/appointment/test_appointment_post.py::test_create_appointment_defaults_to_pending -q
```

- `.env` (ver `.env.example`) é obrigatório até para testes: `src/api/app.py` cria `app = create_app()` no import e exige `DATABASE_URL` carregada por `load_dotenv()` do diretório atual. A API também usa `PASSWORD_PEPPER` e `ADMIN_API_TOKEN`; o agente usa `LLM_BASE_URL`, `OPENAI_API_KEY`, `API_BASE_URL`, `API_AGENT_USER`/`API_AGENT_PASSWORD` (fallback temporário `API_USER`/`API_PASSWORD`) e, opcionalmente, `POLICY_INDEX_PATH` (padrão `~/.cache/llm-trabalho/policy-index`); o benchmark usa `GROQ_API_KEY`/`GEMINI_API_KEY`. Nunca versionar segredos nem dados clínicos reais.

## Arquitetura

- API: `src/api/app.py` registra as blueprints e injeta banco/migrations em `app.extensions`; controllers tratam HTTP, services concentram regras, views formatam JSON e models definem o domínio SQLAlchemy. Autenticação em `src/api/middlewares` (cookie `HttpOnly` ou Bearer administrativo) e autorização por role em `src/api/policies`, não nas controllers nem nos services.
- Migrations Alembic em `infra/alembic/versions` usam `Base.metadata` de `src/api/models/__init__.py`, com `upgrade()` e `downgrade()`. No fluxo normal são aplicadas pela API (`POST /api/migrations` com Bearer `ADMIN_API_TOKEN`), não pelo CLI do Alembic.
- Agente: `src/agent/app.py` → `src/agent/cli.py` (`run_scheduling_flow` interativa; `run_scheduling_case` para execução sem humano). O fluxo real é `build_scheduling_graph` em `src/agent/workflows/scheduling.py` (LangGraph com `MemorySaver`). `poetry run python conferir_grafo.py` mostra nós e arestas sem chamar LLM ou API.
- Agendamento só é gravado após aprovação explícita: `interrupt()` em `src/agent/actions.py`, retomado com `Command(resume={"decision": "approve"|"reject"|"edit", ...})`. O horário é revalidado antes da escrita e a idempotência vive no checkpoint em memória (não sobrevive a reinício do processo).
- Ferramentas em `src/agent/tools.py`, saída validada em `src/agent/output_contract.py`, prompts versionados em `src/prompts` via `load_prompt`. O RAG é a ferramenta `consultar_politica` dentro de `dispatch_tools`, não um nó do grafo; o índice local ainda não contém políticas oficiais. Dados de paciente e agenda vêm da API, nunca do RAG.
- `docs/arquitetura.md` descreve o desenho-alvo: Gestor, Secretária, fila, verificador completo e grade de horários livres ainda não existem.

## Testes e evidências

- Unitários espelham `src` (`tests/unit/api`, `tests/unit/agent`, `tests/unit/prompts`, `tests/unit/evals`); integração em `tests/integration/api/<recurso>/`, separados por método HTTP e por role em `access/`. Cubra sucesso e falha: autenticação, autorização, validação e conflitos.
- Fixtures criam SQLite temporário e aplicam migrations pelo `test_client`; não exigem PostgreSQL. `pythonpath = ["src", "."]` permite imports `api.*`, `src.agent.*` e `cases`. Compartilhe dependências por `app.extensions`.
- `evals/golden_dataset.json` (20 casos) tem teste de forma e cobertura; o contrato normativo é `src/agent/output_contract.py`, não `benchmarks/response.schema.json`. Renomear ferramentas exige atualizar dataset e teste.
- `poetry run python cases.py --case N` e `poetry run python -m src.agent.benchmark` fazem chamadas reais (e possivelmente pagas) e gravam em `logs/`; use `--dry-run` no benchmark antes de uma rodada completa. Ferramentas de casos acadêmicos como `simular_estado_clinica` e `agendar_exames` não existem no agente.

## Respostas ao paciente

- Siga `docs/io.md`: português, `resultado`/`fonte`/`suficiencia` validados, clarificação de entradas incompletas ou ambíguas e nenhuma invenção clínica ou de política. Não exponha segredos nem conteúdo clínico em logs; sem confirmação explícita não há agendamento.
