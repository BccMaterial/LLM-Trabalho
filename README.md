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
