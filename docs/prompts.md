# Etapas - Agente de Priorização

| Etapa                      | Técnica    | Motivo                                                                                          | Contrato de saída            | Como é testada                                                                           |
|----------------------------|------------|-------------------------------------------------------------------------------------------------|------------------------------|------------------------------------------------------------------------------------------|
| Priorização do paciente    | Workflow   | O papel desse agente é retornar um coef. de priorização, e para isso, ele segue um fluxo        | Coeficiente de priorização   | O agente deve retornar o coeficiente, de forma estruturada, onde `0 <= coeficiente <= 1` |

# Etapas - Agente de Agendamento

| Etapa                      | Técnica    | Motivo                                                    | Contrato de saída                                          | Como é testada                                                                                  |
|----------------------------|------------|-----------------------------------------------------------|------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| Triagem                    | Roteamento | O agente precisa saber o que o paciente quer fazer        | Rota que o agente vai seguir                               | Teste unitário com diferentes entradas de texto (Retorno = "agendamento", "orientação", etc.)   |
| Sugestão de Agendamentos   | Workflow   | Para determinar as agendas do paciente, segue-se um fluxo | Lista de agendamentos para o paciente                      | Validação se o agente retornou uma lista de agendamentos, e solicitou o agendamento do paciente |
| Orientação para o paciente | Reasoning  | Utilizado para orientar o paciente, com guardrails        | Texto livre, gerado pelo modelo utilizando reasoning       | Validação se o agente retornou uma lista de agendamentos, e solicitou o agendamento do paciente |
