# LLM-Trabalho

Agente de agendamentos para avaliações neuropsicológicas, com priorização de pacientes baseado em simulações de exames e histórico do paciente.

## Grupo

- Caio Troiano
- Thiago Lins
- Vinicius Vianna

# Setup

Para executar o projeto, siga os passos abaixo.

## Pré-requisitos

- Python 3.14 ou superior
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

Execução do agente:
```bash
poetry run task dev:agent
```

Execução dos testes automatizados:
```bash
poetry run test
```

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
