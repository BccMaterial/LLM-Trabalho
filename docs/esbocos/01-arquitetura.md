## 1. Entrada

Recebemos (ou podemos receber) os seguintes dados do paciente:
- Suspeita do paciente
- Reclamações de demora
- Solicitação de agenda
- Exames marcados
- Dados do cliente

O agente é disparado pelo próprio paciente, através de mensagens.

Estima-se que 60% das interações sejam para marcar agenda, 10% reclamações, 10% para consultar o andamento da fila de atendimento e 20% perguntas gerais.

## 2. System

**System prompt:** "Você é um organizador de agendas de uma clínica de avaliação neuropsicológica,  que deve agendar os exames dos pacientes com base em sua prioridade"

O agente conversa com um subagente, especializado em definir a prioridade do paciente

Ferramentas:
- **Simulação dos exames:** Com base no estado atual da clínica e na suspeita do paciente, estima a duração até o diagnóstico do paciente
- **API da Clínica:** Recebe os dados cadastrais do cliente, permitindo que seja avaliado o histórico do paciente.

O que precisa ser armazenado:
- Quem é o paciente
- A prioridade do paciente
- Se já possui agendamento ou não
- As sugestões de agendas fornecida pelo agente
- Disponibilidade de agenda

Orçamento:
- **Passos:** No mínimo 5 passos, e no máximo 10.
- **Tokens:** Até 1500 tokens
- **Tempo:** 2 minutos, mas pode aumentar de acordo com a escolha do modelo, e da quantidade de reprocessamento de agendas

## 3. Processamento

### Fluxo
- **ENTRADA:** Mensagem livre do paciente
- **TRIAGEM:** Classifica em 4 rotas (Agendamento - Segue pra análise, consulta de dados, reclamação, orientações)
- **PRIORIZAÇÃO:** Chama o agente de priorização, que retorna o quão prioritário é o cliente com base em seus dados
- **ANÁLISE:** Com o retorno do agente de priorização, analisa as possíveis agendas
- **VALIDAÇÃO:** Verifica a disponibilidade, retorna as agendas para o paciente, e pergunta se ele deseja marcar
- **REGISTRO:** Marca as agendas para o paciente
- **RETORNO:** Avisa ao paciente se marcou ou não

### Entrada e saída

**Triagem:**
- Entra: Texto do paciente
- Sai: Rota que o agente vai seguir

**Priorização:**
- Entra: Dados do cliente, suspeita e histórico 
- Sai: Prioridade do paciente

**Análise:**
- Entra: Prioridade do paciente
- Sai: Sugestões de agenda

**Retorno:**
- Sai: Mensagem com as sugestões para o paciente

## Justificativa

Escolhemos o roteamento e o fluxo sequencial, pois por ser um chat, o cliente pode pedir mais de uma coisa. Além disso, escolhemos a criação de um agente especializado em priorização porque a priorização depende de diversos fatores, que não precisam do contexto inteiro da conversa com o agente principal, mas depende dos dados inseridos.
