# Integrantes do grupo

O grupo é composto pelos seguintes integrantes:
- Caio Troiano
- Thiago Lins
- Vinicius Vianna

# Indústria & Problema

**Setor:** Indústria da saúde, Psicologia

## Problema

A clínica apresenta problemas de organização e priorização da fila de atendimento, gerando longos tempos de espera de maneira inconsistente. A ausência da priorização gera diagnósticos demorados em casos graves, no qual é recomendado o início do tratamento o mais rápido possível.

## Contexto

Em uma clínica especializada em diagnósticos a partir de Avaliações Neuropsicológicas, a priorização e a organização da fila é arbitrária, gerando longos tempos de espera de maneira inconsistente. 

Além disso, há reclamações e desistências frequentes. A ausência da priorização gera diagnósticos demorados em casos graves, no qual é recomendado o início do tratamento o mais rápido possível.

O agente irá ser executado a partir da interação do paciente, que pode ser feita através de mensagens. A partir do agente que interage com o paciente, será executado um outro agente para decidir qual a priorização daquele paciente, com base em simulações, histórico do paciente e preferência de horário. Após a priorização, o agente que conversa com o paciente para validar as agendas.

Como regras de domínio temos:
- **Quantidade de exames:** A clínica possui uma quantidade máxima de exames, que são realizados por profissionais especializados. A quantidade de exames disponíveis é limitada, e a clínica não possui capacidade de aumentar a quantidade de exames disponíveis. Atualmente um paciente pode realizar entre 4 a 6 exames, dependendo do caso.
- **Agendamentos:** O agendamento é feito de acordo com a preferência do paciente. Caso haja disponibilidade no horário escolhido, o paciente é agendado. Caso não haja disponibilidade, o paciente é informado e pode escolher outro horário.
- **Encaminhamentos:** Para realizar os exames, o paciente precisa de um encaminhamento médico. Seja ele vindo de um médico de outra clínica ou da própria clínica.

## Usuários

| Perfil   | O que ele quer                        | O que ele sabe                                      | O que ele pode saber |
|----------|---------------------------------------|-----------------------------------------------------|----------------------|
| Usuários | Facilidade e agilidade no atendimento | Sua suspeita, seus dados, e preferências de horário | Seus agendamentos    |

## Ganhos esperados

Espera-se que haja uma redução de aproximadamente 10% na fila de espera, de forma que não haja um custo muito elevado em relação à contratação de funcionários novos. É possível que com o aumento do fluxo de pessoas por conta da espera menor tenha como consequência um lucro maior.

# Arquitetura do agente

Será desenvolvido dois agentes:
- **Agente Conversacional:** Responsável por conversar com o paciente, coletar informações e fornecer sugestões de agendamento.
- **Agente de Priorização:** Responsável por analisar os dados do paciente, simular os exames e definir a prioridade do paciente.

## Agente Conversacional

Agente especializado em conversar com o paciente.

### Entrada

Recebemos (ou podemos receber) os seguintes dados do paciente:
- Suspeita do paciente
- Reclamações de demora
- Solicitação de agenda
- Exames marcados
- Dados do cliente

O agente é disparado pelo próprio paciente, através de mensagens.

Estima-se que 60% das interações sejam para marcar agenda, 10% reclamações, 10% para consultar o andamento da fila de atendimento e 20% perguntas gerais.

### System

**System prompt:** "Você é um organizador de agendas de uma clínica de avaliação neuropsicológica,  que deve agendar os exames dos pacientes com base em sua prioridade".

O agente conversa com um subagente, especializado em definir a prioridade do paciente.

Ferramentas:
- **Agente de priorização:** Com base no estado atual da clínica e na suspeita do paciente, estima a duração até o diagnóstico do paciente.
- **API da Clínica:** Marca os agendamentos dos pacientes.

O que precisa ser armazenado:
- Quem é o paciente
- A prioridade do paciente
- Se já possui agendamento ou não
- As sugestões de agendas fornecida pelo agente

Orçamento:
- **Passos:** No mínimo 5 passos, e no máximo 10.
- **Tokens:** Até 1500 tokens
- **Tempo:** 2 minutos, mas pode aumentar de acordo com a escolha do modelo, e da quantidade de reprocessamento de agendas

### Processamento

Fluxo:
- **ENTRADA:** Mensagem livre do paciente
- **TRIAGEM:** Classifica em 4 rotas (Agendamento - Segue pra análise, consulta de dados, reclamação, orientações)
- **ANÁLISE:** Caso seja um agendamento, com o retorno do agente de priorização, analisa as possíveis agendas
- **VALIDAÇÃO:** Verifica a disponibilidade, retorna as agendas para o paciente, e pergunta se ele deseja marcar
- **REGISTRO:** Marca as agendas para o paciente
- **RETORNO:** Avisa ao paciente se as agendas foram marcadas ou não.

Entrada e saída:

**Triagem:**
- Entra: Texto do paciente
- Sai: Rota que o agente vai seguir

**Priorização:**
- Entra: Dados do cliente, suspeita e histórico 
- Sai: Prioridade do paciente

**Análise:**
- Entra: Prioridade do paciente
- Sai: Sugestões de agenda

**Validação:**
- Entra: Sugestões de agenda
- Sai: Disponibilidade de agenda

**Registro:**
- Entra: Disponibilidade de agenda para a API
- Sai: Retorno da API

**Retorno:**
- Entra: Status do agendamento (Retorno da API)
- Sai: Mensagem com as sugestões para o paciente

#### Justificativa

Escolhemos o roteamento e o fluxo sequencial, pois por ser um chat, o cliente pode pedir mais de uma coisa. Além disso, escolhemos a criação de um agente especializado em priorização porque a priorização depende de diversos fatores, que não precisam do contexto inteiro da conversa com o agente principal, mas depende dos dados inseridos.

## Agente de Priorização

Agente especializado em priorizar os pacientes com base em seus dados.

### Entrada

Recebemos (ou podemos receber) os seguintes dados do agente conversacional:
- Suspeita do paciente
- Histórico do paciente (Laudos de exames anteriores, se houver)
- Preferências de horário
- Dados do cliente

O agente é disparado pelo agente conversacional.

Estima-se que 60% das interações sejam para marcar agenda, 10% reclamações, 10% para consultar o andamento da fila de atendimento e 20% perguntas gerais.

Todas as interações com esse agente será realizada a partir do agente conversacional.

### System

**System prompt:** "Você é um agente especializado em agendamentos com base em prioridade. Sua responsabilidade é receber dados de um agente conversacional, e com base neles e em simulações, retornar um coeficiente de priorização daquele paciente, juntamente com as sugestões de agenda".

Ferramentas:
- **Simulador de exames:** Com base no estado atual da clínica e na suspeita do paciente, estima a duração até o diagnóstico do paciente.
- **API da Clínica:** Pode ser utilizado para buscar os agendamentos

O que precisa ser armazenado:
- Quem é o paciente
- Resultado das simulações
- Se já possui agendamento ou não

Orçamento:
- **Passos:** No mínimo 5 passos, e no máximo 10.
- **Tokens:** Até 15000 tokens
- **Tempo:** 2 minutos, mas pode aumentar de acordo com a escolha do modelo, e da quantidade de reprocessamento de agendas

### Processamento

Fluxo:
- **ENTRADA:** Dados do paciente;
- **ANÁLISE:** Com base nos dados do paciente e nos agendamentos já existentes, realiza simulações para estimar o tempo até o diagnóstico do paciente e define o coeficiente de priorização;
- **VALIDAÇÃO:** Verifica se a agenda não conflita com outros agendamentos;
- **RETORNO:** Retorna para o agente conversacional o coeficiente de priorização, junto com as sugestões de agenda.

Entrada e saída:

**Análise:**
- Entra: Dados do paciente e da clínica
- Sai: Coeficiente de priorização

**Validação:**
- Entra: Coeficiente de validação, resultado das simulações e dados do paciente
- Sai: Sugestões de agenda

**Retorno:**
- Entra: Status do agendamento (Retorno da API)
- Sai: Mensagem com as sugestões para o paciente

#### Justificativa

Escolhemos um fluxo sequencial, pois é um agente que possui um fluxo bem definido, e não depende do contexto da conversa com o paciente. Além disso, escolhemos a criação de um agente especializado em priorização porque a priorização depende de diversos fatores, que não precisam do contexto inteiro da conversa com o agente principal, mas depende dos dados inseridos.


