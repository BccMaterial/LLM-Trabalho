# Model card do sistema

## Identificação

**Nome:** Atendente e apoio operacional para avaliações neuropsicológicas.  
**Versão documental:** desenho-alvo dos agentes Atendente, Gestor e Secretária.  
**Estado:** há um protótipo de agente Atendente com API local; o desenho de três agentes, o verificador completo e as proteções de produção ainda não estão implementados. Ver `README.md` e `docs/case.md`.

## Finalidade e usuários

Atender pacientes/responsáveis por mensagem, apoiar agendamento, organizar pendências administrativas e ajudar a equipe autorizada a conferir a fila e a agenda. O paciente/responsável é o usuário principal. Recepção/secretaria, gestor e responsável autorizado da clínica são usuários internos secundários.

## Fora de escopo

- Diagnóstico, prognóstico, recomendação de tratamento ou avaliação de gravidade clínica.
- Estimativa de duração de exames ou prazo de diagnóstico.
- Priorização clínica baseada em inferência livre do modelo.
- Regras de cancelamento, remarcação ou documentação não aprovadas pela clínica.
- Decisão clínica ou alteração de fila sem critério formal e revisão prevista.

## Autoridade e aprovações

O modelo pode classificar intenção, solicitar dados, resumir resultados autorizados e preparar opções. O código valida autorização, schemas, disponibilidade e confirmação. O paciente confirma a reserva. Um responsável da clínica aprova as regras de prioridade e revisa exceções. A escrita não é feita pelo modelo; a API executa a operação validada. Não há exclusão física de registros prevista.

## Ferramentas e integrações

| Integração | Agente usuário | Permissão proposta | Estado |
|---|---|---|---|
| API de cadastro/encaminhamento | Atendente, Secretária | Consulta autorizada; tarefas administrativas limitadas | API local tem usuários; encaminhamento clínico não está modelado |
| API de fila/agenda | Atendente, Gestor | Consulta de estado e disponibilidade | A API local lista agendamentos, mas não calcula horários livres nem tem fila clínica |
| API de agendamento | Controlador após confirmação | Gravação validada, idempotente e auditada | API local grava agendamentos; confirmação determinística e idempotência do agente ainda pendentes |
| Base de políticas oficiais | Secretária, Atendente, Gestor | Consulta somente leitura | RAG descrito como proposta, sem índice no código |
| Verificador determinístico | Controlador | Validação independente do modelo | Não implementado |

## Dados

Podem existir dados de saúde sensíveis, incluindo suspeita, laudo, encaminhamento e histórico. O sistema deve minimizar os campos consultados, usar identidade autenticada, separar metadados da mensagem e manter dados clínicos na API oficial. Não usar dados de pacientes para treinamento. Não copiar laudos ou conversas completas para memória do agente. Logs guardam somente o mínimo operacional necessário, com retenção e acesso definidos pela clínica.

## Avaliação e critério de sucesso

Avaliar separadamente: (1) validade de tool calls e schemas; (2) correção da fonte; (3) concordância com critérios de prioridade aprovados; (4) disponibilidade/consistência das opções; (5) confirmações antes de escrita; (6) tratamento de insuficiência e escalonamento. O benchmark sintético foi executado em sete casos por modelo; os resultados estão em `docs/modelos.md` e `logs/model-benchmark/`. O verificador completo na aplicação ainda não está implementado.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Prioridade incorreta ou sem respaldo | Regra formal/versionada, verificador independente e revisão humana quando faltar evidência |
| Vazamento de dado de saúde | Minimização, autenticação, separação por tarefa, logs minimizados e controles de acesso |
| Agendamento indevido | Confirmação explícita, revalidação no momento da escrita, idempotência e auditoria |
| Política ausente/desatualizada | Resposta insuficiente e encaminhamento; nunca completar por suposição |
| API indisponível ou inconsistente | Não reutilizar disponibilidade antiga; informar falha e criar encaminhamento |

## Supervisão, registro e retenção

Pessoas autorizadas da clínica podem revisar a fonte, a regra aplicada, os resultados do verificador e os registros técnicos; podem interromper o fluxo. A clínica precisa definir retenção, consentimento, acesso e procedimento de correção antes de usar dados reais. Esta documentação não define prazo legal de retenção.

## Limites conhecidos

Nenhum modelo foi aprovado para uso com pacientes; Gemini 3.5 Flash-Lite é candidato provisório para novos testes. O agente inicia com mensagem demonstrativa, mantém turnos e chama ferramentas pela API local. Ainda falta registrar quatro execuções de integração do agente como logs separados e validar em código toda escrita; o JSON do benchmark registra trajetórias distintas, mas usa ferramentas simuladas no próprio processo.
