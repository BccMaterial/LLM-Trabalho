# LLM-Trabalho

Protótipo acadêmico para apoiar atendimento, fila e agenda de uma clínica de avaliações neuropsicológicas, com três papéis de agente: Atendente, Gestor e Secretária. O sistema não simula exames nem estima prazo de diagnóstico.

## Grupo

- Caio Troiano
- Thiago Lins
- Vinicius Vianna

# Setup

Para executar o projeto, siga os passos abaixo.

## Pré-requisitos

- Python 3.12 ou superior
- Poetry

## Inicialização do projeto

### Instalação - Poetry

Para instalar o poetry, pode se utilizar as seguintes opções:

`pip` global:
```bash
pipx install poetry
```

Via script (Linux, macOs, Windows - WSL):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Via script (Powershell):
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

### Dependências e .env

Com o poetry instalado, execute:
```bash
poetry install
```
Com isso, as dependências do projeto serão instaladas.

Após a instalação, preencha os valores da `.env` com base no `.env.example`:
```bash
LLM_BASE_URL="<YOUR_LLM_BASE_URL>"
OPENAI_API_KEY="<YOUR_OPENAI_API_KEY>"
LLM_MODEL="<YOUR_LLM_MODEL>"
```
Para a API, configure também `DATABASE_URL`, `PASSWORD_PEPPER` e `ADMIN_API_TOKEN` conforme o `.env.example`. Não versionar nem registrar os valores secretos.

### Execução de código

Execução da API:
```bash
poetry run task dev:api
```

Execução da API e do PostgreSQL com Docker:
```bash
docker compose --env-file .env -f infra/compose.yaml up --build
```

Para encerrar os serviços, pressione `Ctrl+C`.

Defina `ADMIN_API_TOKEN` no ambiente do terminal com o mesmo valor configurado no `.env`. As migrations podem então ser consultadas e aplicadas pela API:
```bash
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" http://localhost:5000/api/migrations
curl -X POST -H "Authorization: Bearer $ADMIN_API_TOKEN" http://localhost:5000/api/migrations
```

Execução do agente:
```bash
poetry run task dev:agent
```

Ao iniciar, o agente fica em modo convidado. Os comandos disponíveis no
terminal são:

- `/login`: autentica a conta do usuário com e-mail e senha;
- `/help`: mostra os comandos disponíveis;
- `/sair`: encerra o atendimento.

Para chamadas à API, configure uma conta técnica própria com
`API_AGENT_USER` e `API_AGENT_PASSWORD`. `API_USER` e `API_PASSWORD` continuam
como fallback temporário. O login do usuário não é enviado ao LLM nem misturado
com o cookie técnico usado pelo agente.

Execução dos testes automatizados:
```bash
poetry run task test
```

## Estado do projeto

A arquitetura e os contratos estão descritos em [`docs/case.md`](docs/case.md), [`docs/arquitetura.md`](docs/arquitetura.md) e [`docs/io.md`](docs/io.md). O código atual ainda é um protótipo: a API Flask tem recursos de profissionais e o agente envia uma mensagem fixa ao modelo. Ainda não há integração de paciente/agenda, laço conversacional, três agentes, ferramentas do domínio, verificador ou benchmark executado. A documentação distingue o desenho-alvo desses recursos ainda pendentes.

## Autenticação da API

O login cria uma sessão persistida no servidor e entrega o identificador somente em um cookie `HttpOnly`:

- `POST /api/sessions` com `email` e `password`: inicia uma sessão.
- `GET /api/sessions`: retorna os dados do usuário e a expiração da sessão atual.
- `DELETE /api/sessions`: revoga a sessão atual e remove o cookie.

O cookie usa `SameSite=Lax`; `SESSION_TTL_SECONDS` define sua duração (padrão: `86400`, 24 horas). `SESSION_COOKIE_SECURE` deve permanecer habilitado em produção; para desenvolvimento local sem HTTPS, pode ser desabilitado no `.env`.

As rotas de usuários aplicam `UserAuthorizationPolicy`: a administração gerencia contas, e cada usuário pode atualizar apenas os próprios campos permitidos. As rotas de profissionais aceitam `admin` e `manager`; as rotas de migrations aceitam somente `admin`. `ADMIN_API_TOKEN` é uma credencial administrativa alternativa enviada como Bearer token e pode ser usada para essas operações. `/api/example` permanece pública.

# Contrato de entrada e saída

O sistema recebe texto livre em linguagem natural. O texto do usuário é a entrada principal. Qualquer dado que acompanhe a conversa sem ser digitado pelo paciente — por exemplo `thread_id`, `session_id`, `user_id` ou `case_id` — deve ser tratado como metadado do contexto e não como parte da pergunta em si.

## Entrada

- A entrada do sistema é texto livre, em linguagem natural.
- O agente deve interpretar a intenção do usuário, identificar lacunas, ambiguidades e limites de escopo.
- Caso a entrada esteja incompleta ou ambígua, o sistema deve perguntar ou recusar de forma explícita.
- Arquivos, imagens, planilhas e outros artefatos podem ser usados por ferramenta, mas não substituem a pergunta em texto do usuário.

## Saída

A saída do sistema deve ser um objeto validado, com os campos obrigatórios abaixo:

- `resultado`: a resposta, decisão, documento ou ação a ser executada;
- `fonte`: a evidência que sustenta a resposta, como trecho do corpus, registro, ferramenta ou contexto consultado;
- `suficiencia`: indica se a base era suficiente para responder (`"suficiente"` ou `"insuficiente"`).

Schema de referência:

```python
from typing import Any, Literal
from pydantic import BaseModel

class SaidaSistema(BaseModel):
    resultado: Any
    fonte: Any
    suficiencia: Literal["suficiente", "insuficiente"]
```

## Casos que exigem recusa ou clarificação

O sistema deve tratar explicitamente os cenários abaixo:

- entrada incompleta: pedir o que falta ou recusar dizendo o que falta;
- entrada ambígua: desambiguar perguntando ou escolher e declarar a escolha;
- entrada fora do escopo: recusar e dizer o que o sistema faz.

Esses casos fazem parte do contrato e não são improvisos.

A documentação completa e os exemplos ficam em `docs/io.md`.
