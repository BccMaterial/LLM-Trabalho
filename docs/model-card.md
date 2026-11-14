# Model card do sistema

## Identificação

**Nome:** Atendente e apoio operacional para avaliações neuropsicológicas.  
**Versão documental:** desenho-alvo dos agentes Atendente, Gestor e Secretária.  
**Estado:** protótipo atual não implementa esse desenho; ver `README.md` e `docs/case.md`.

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
| API de cadastro/encaminhamento | Atendente, Secretária | Consulta autorizada; tarefas administrativas limitadas | Não integrada ao agente |
| API de fila/agenda | Atendente, Gestor | Consulta de estado e disponibilidade | Não há endpoint de agenda no código atual |
| API de agendamento | Controlador após confirmação | Gravação validada, idempotente e auditada | Não implementada |
| Base de políticas oficiais | Secretária, Atendente, Gestor | Consulta somente leitura | RAG descrito como proposta, sem índice no código |
| Verificador determinístico | Controlador | Validação independente do modelo | Não implementado |

## Dados

Podem existir dados de saúde sensíveis, incluindo suspeita, laudo, encaminhamento e histórico. O sistema deve minimizar os campos consultados, usar identidade autenticada, separar metadados da mensagem e manter dados clínicos na API oficial. Não usar dados de pacientes para treinamento. Não copiar laudos ou conversas completas para memória do agente. Logs guardam somente o mínimo operacional necessário, com retenção e acesso definidos pela clínica.

## Avaliação e critério de sucesso

Avaliar separadamente: (1) validade de tool calls e schemas; (2) correção da fonte; (3) concordância com critérios de prioridade aprovados; (4) disponibilidade/consistência das opções; (5) confirmações antes de escrita; (6) tratamento de insuficiência e escalonamento. Meta de 100% para gravações confirmadas e compatíveis com a API, medida sobre todas as tentativas de gravação. Benchmark e verificador ainda não foram executados/implementados.

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

O modelo candidato ainda não foi escolhido. A comparação de modelos não foi executada. O agente atual carrega o prompt versionado do Atendente, mas envia uma mensagem fixa, não chama ferramentas, não mantém laço e não registra os quatro casos com logs.
