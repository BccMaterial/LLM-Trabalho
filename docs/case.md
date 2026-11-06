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

O agente será executado a partir da interação do paciente, que pode ser feita através de mensagens. O agente conversacional aciona o agente de priorização, encaminhando os dados autorizados do paciente e os insumos obtidos da lista atual de agendamentos consultada pela API. O agente de priorização retorna um coeficiente; com esse resultado, a preferência do paciente e a disponibilidade consultada na API, o agente conversacional gera sugestões de agenda.

Como regras de domínio temos:
- **Quantidade de exames:** A clínica possui uma quantidade máxima de exames, que são realizados por profissionais especializados. A quantidade de exames disponíveis é limitada, e a clínica não possui capacidade de aumentar a quantidade de exames disponíveis. Atualmente um paciente pode realizar entre 4 a 6 exames, dependendo do caso.
- **Agendamentos:** O agendamento é feito de acordo com a preferência do paciente. Caso haja disponibilidade no horário escolhido, o paciente é agendado. Caso não haja disponibilidade, o paciente é informado e pode escolher outro horário.
- **Encaminhamentos:** Para realizar os exames, o paciente precisa de um encaminhamento médico. Seja ele vindo de um médico de outra clínica ou da própria clínica.

## Justificativa

A escolha do uso de agentes de IA para esse problema se dá por conta da complexidade do problema, que envolve a priorização de pacientes com base em diversos fatores, como histórico médico, suspeita do paciente e preferências de horário. Além disso, a utilização de agentes permite uma maior agilidade no atendimento, reduzindo o tempo de espera dos pacientes e aumentando a satisfação dos mesmos, juntamente com a redução do gasto se comparar com a nova contratação de funcionários para suprir essa demanda.

## Usuários

| Perfil   | O que ele quer                        | O que ele sabe                                      | O que ele pode saber |
|----------|---------------------------------------|-----------------------------------------------------|----------------------|
| Usuários | Facilidade e agilidade no atendimento | Sua suspeita, seus dados, e preferências de horário | Seus agendamentos    |

## Ganhos esperados

Espera-se que haja uma redução de aproximadamente 10% na fila de espera, de forma que não haja um custo muito elevado em relação à contratação de funcionários novos. É possível que com o aumento do fluxo de pessoas por conta da espera menor tenha como consequência um lucro maior.

# Arquitetura do agente

Será desenvolvido dois agentes:
- **Agente Conversacional:** Responsável por conversar com o paciente, coletar informações e fornecer sugestões de agendamento.
- **Agente de Priorização:** Responsável por analisar os dados autorizados do paciente conforme os critérios definidos para o projeto e retornar um coeficiente de priorização. Pode receber insumos derivados da lista de agendamentos consultada na API.

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

**System prompt:** "Você é um organizador de agendas de uma clínica de avaliação neuropsicológica,  que deve agendar os exames dos pacientes com base em sua prioridade. Além disso, você pode orientar os pacientes dependendo da sua pergunta, seja uma reclamação, dúvidas sobre processos e consulta de dados".

O agente conversa com um subagente, especializado em definir a prioridade do paciente.

Ferramentas:
- **Agente de priorização:** Analisa os dados do paciente e retorna um coeficiente estruturado.
- **API da Clínica:** Consulta os dados do paciente e a lista de agendamentos, valida disponibilidade e registra agendamentos após confirmação do paciente.

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
- **ANÁLISE:** Encaminha os dados do paciente e os insumos da API ao agente de priorização; com o coeficiente retornado, a preferência do paciente e a disponibilidade consultada, gera sugestões de agenda
- **VALIDAÇÃO:** Verifica a disponibilidade, retorna as agendas para o paciente, e pergunta se ele deseja marcar
- **REGISTRO:** Marca as agendas para o paciente
- **RETORNO:** Avisa ao paciente se as agendas foram marcadas ou não.

Entrada e saída:

**Triagem:**
- Entra: Texto do paciente
- Sai: Rota que o agente vai seguir

**Priorização:**
- Entra: Dados do cliente, suspeita, histórico e insumos derivados da lista de agendamentos consultada pela API
- Sai: Coeficiente de priorização estruturado

**Análise:**
- Entra: Coeficiente retornado pelo agente de priorização, preferência do paciente e disponibilidade consultada pela API
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

**System prompt:** "Você é um agente especializado em priorização de pacientes para agendamentos. Sua responsabilidade é receber dados autorizados de um agente conversacional e retornar um coeficiente de priorização estruturado, considerando os critérios definidos para o projeto e os insumos gerados a partir da lista de agendamentos consultada pela API."

Ferramentas:
- **API da Clínica:** Consulta os dados do paciente e a lista atual de agendamentos, que são usados para gerar insumos para priorização.

O que precisa ser armazenado:
- Quem é o paciente
- Coeficiente de priorização
- Se já possui agendamento ou não

Orçamento:
- **Passos:** No mínimo 5 passos, e no máximo 10.
- **Tokens:** Até 15000 tokens
- **Tempo:** 2 minutos, mas pode aumentar de acordo com a escolha do modelo, e da quantidade de reprocessamento de agendas

### Processamento

Fluxo:
- **ENTRADA:** Dados do paciente;
- **CONSULTA:** Obtém pela API a lista atual de agendamentos e prepara insumos para priorização;
- **ANÁLISE:** Recebe os dados do paciente e os insumos derivados da API, aplica os critérios definidos para o projeto e retorna o coeficiente de priorização;
- **RETORNO:** Envia o coeficiente ao agente conversacional, que o usa com a preferência do paciente e a disponibilidade da API para gerar sugestões de agenda.

Entrada e saída:

**Análise:**
- Entra: Dados do paciente e insumos derivados dos agendamentos consultados pela API
- Sai: Coeficiente de priorização

**Validação:**
- Entra: Coeficiente calculado
- Sai: Coeficiente validado conforme o schema de saída

**Retorno:**
- Entra: Coeficiente de priorização
- Sai: Coeficiente estruturado para o agente conversacional

#### Justificativa

Escolhemos um fluxo sequencial, pois é um agente que possui um fluxo bem definido, e não depende do contexto da conversa com o paciente. Além disso, escolhemos a criação de um agente especializado em priorização porque a priorização depende de diversos fatores, que não precisam do contexto inteiro da conversa com o agente principal, mas depende dos dados inseridos.
