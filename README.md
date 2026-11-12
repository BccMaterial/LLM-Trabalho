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

As migrations podem ser consultadas e aplicadas pela API:
```bash
curl http://localhost:5000/api/migrations
curl -X POST http://localhost:5000/api/migrations
```

Execução do agente:
```bash
poetry run task dev:agent
```

Execução dos testes automatizados:
```bash
poetry run task test
```

## Estado do projeto

A arquitetura e os contratos estão descritos em [`docs/case.md`](docs/case.md), [`docs/arquitetura.md`](docs/arquitetura.md) e [`docs/io.md`](docs/io.md). O código atual ainda é um protótipo: a API Flask tem recursos de profissionais e o agente envia uma mensagem fixa ao modelo. Ainda não há integração de paciente/agenda, laço conversacional, três agentes, ferramentas do domínio, verificador ou benchmark executado. A documentação distingue o desenho-alvo desses recursos ainda pendentes.

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
