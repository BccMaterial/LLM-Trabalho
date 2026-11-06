# Etapas - Agente de Priorização

| Etapa                      | Técnica    | Motivo                                                                                          | Contrato de saída            | Como é testada                                                                           |
|----------------------------|------------|-------------------------------------------------------------------------------------------------|------------------------------|------------------------------------------------------------------------------------------|
| Consulta de agendamentos   | Workflow   | A API é a fonte atual dos registros de agenda; os dados consultados geram insumos para priorização | Lista de agendamentos e insumos derivados | Conferir chamada à API, filtros autorizados e correspondência dos insumos aos registros retornados |
| Priorização do paciente    | Workflow   | O agente recebe os dados do paciente e os insumos da API, segue os critérios definidos e retorna o coeficiente | Coeficiente de priorização | O agente retorna o coeficiente de forma estruturada, onde `0 <= coeficiente <= 1` |

# Etapas - Agente de Agendamento

| Etapa                      | Técnica    | Motivo                                                    | Contrato de saída                                          | Como é testada                                                                                  |
|----------------------------|------------|-----------------------------------------------------------|------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| Triagem                    | Roteamento | O agente precisa saber o que o paciente quer fazer        | Rota que o agente vai seguir                               | Teste unitário com diferentes entradas de texto (Retorno = "agendamento", "orientação", etc.)   |
| Sugestão de Agendamentos   | Workflow   | O agente conversacional usa o coeficiente, a preferência do paciente e a disponibilidade consultada pela API | Lista de horários sugeridos | Conferir disponibilidade na API e consistência das sugestões com o coeficiente e a preferência |
| Orientação para o paciente | Reasoning  | Utilizado para orientar o paciente, com guardrails        | Texto livre, gerado pelo modelo utilizando reasoning       | Validação se o agente retornou uma lista de agendamentos, e solicitou o agendamento do paciente |
