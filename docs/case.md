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

## Agentes

- **Agente 1:** Responsável por atender o cliente;
- **Agente 2:** Responsável pela priorização do paciente a partir das simulações, dados fornecidos, organização da fila e agendamentos de todos os pacientes.

# Workflow do agente

TODO: Escrever sobre o workflow
