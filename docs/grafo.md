# Grafo do agente

Este documento descreve o grafo compilado por
`src/agent/workflows/scheduling.py::build_scheduling_graph`, usado pelo CLI em
`src/agent/cli.py::run_scheduling_flow`. O diagrama-alvo da arquitetura não
representa funcionalidades que ainda não existem; este arquivo registra o
comportamento executado.

## Inspecionar o grafo compilado

Na raiz do repositório, execute:

```text
poetry run python conferir_grafo.py
```

O script importa e compila `build_scheduling_graph`, o mesmo builder usado
pelo CLI. As dependências são placeholders apenas durante a compilação; o
script não executa nós nem faz chamadas ao LLM ou à API. A saída atual está
registrada junto ao diagrama em [`arquitetura.md`](./arquitetura.md).
`__start__` e `__end__` são sentinelas do LangGraph, não nós de negócio.

## Nós executados

| Nó | Responsabilidade | Decisão e estado principal |
|---|---|---|
| `call_model` | Envia histórico e ferramentas ao LLM, valida a resposta e registra tool calls | O modelo escolhe responder ou solicitar ferramenta; o nó aplica orçamento, conta tokens e atualiza `messages`, `pending_action`, `round_count` e `proposal_version` |
| `validate_professional` | Confere se o profissional da proposta está ativo | Código lê `pending_action`, consulta a API e escreve `professional_name` e `professional_validated` |
| `request_approval` | Solicita aprovação dos argumentos exatos da proposta | `actions.request_appointment_approval` chama `interrupt`; registra decisão, chave idempotente e prazo de aprovação |
| `revalidate_availability` | Consulta novamente a disponibilidade após a aprovação | Código preserva ou limpa `pending_action` antes de permitir a escrita |
| `dispatch_tools` | Executa tool calls e anexa resultados; evita repetir uma ação concluída | Exige aprovação para `confirmar_agendamento`, atualiza `tool_results` e `completed_actions`; também aplica o orçamento |
| `require_authentication` | Informa que `/login` é necessário para agendar | Encerra o turno sem executar a escrita |

O CLI mantém o loop de conversa fora do grafo. Ele reinicia os contadores por
turno, estabelece um deadline, invoca o grafo e imprime a resposta. Para uma
proposta interrompida, retoma com `Command(resume=...)` usando o mesmo
`thread_id`.

## Arestas e decisões de roteamento

As bifurcações condicionais são decididas por funções/lambdas em Python. O
modelo escolhe uma resposta ou tool call; não escolhe os destinos do grafo.
Não há roteamento por embedding.

| Origem | Quem decide | Condição | Destino |
|---|---|---|---|
| `START` | `route_from_start` (código) | Há ação pendente sem resultado de aprovação; o profissional já foi validado | `request_approval` |
| `START` | `route_from_start` (código) | Há ação pendente sem resultado de aprovação; o profissional ainda precisa ser validado | `validate_professional` |
| `START` | `route_from_start` (código) | Não há ação aguardando aprovação | `call_model` |
| `call_model` | Modelo escolhe; `route_after_model` (código) verifica o estado | Há término ou não há tool call pendente | `END` |
| `call_model` | Modelo escolhe; `route_after_model` (código) verifica autenticação | Ação é agendamento e não há `authenticated_user` | `require_authentication` |
| `call_model` | Modelo escolhe; `route_after_model` (código) valida o destino | Ação é agendamento autenticado | `validate_professional` |
| `call_model` | Modelo escolhe; `route_after_model` (código) valida o destino | Outra tool call | `dispatch_tools` |
| `validate_professional` | `route_after_professional_validation` (código) | A validação terminou com erro ou limite | `END` |
| `validate_professional` | `route_after_professional_validation` (código) | Profissional válido | `request_approval` |
| `request_approval` | `route_after_approval` (código) | Ação aprovada | `revalidate_availability` |
| `request_approval` | `route_after_approval` (código) | Ainda não há decisão; a proposta requer validação do profissional | `validate_professional` |
| `request_approval` | `route_after_approval` (código) | Ainda não há decisão; o profissional já foi validado | `request_approval` |
| `request_approval` | `route_after_approval` (código) | Resposta inválida, marcada como `approval_decision="invalid"`; mantém a ação pendente para a próxima invocação | `END` |
| `request_approval` | `route_after_approval` (código) | Ação rejeitada, aprovação expirada ou outro término | `END` |
| `revalidate_availability` | Lambda do grafo (código) | `pending_action` permanece definida após revalidar | `dispatch_tools` |
| `revalidate_availability` | Lambda do grafo (código) | Proposta inválida, horário indisponível, erro ou limite | `END` |
| `dispatch_tools` | `route_after_tools` (código) | Há motivo de término ou status final de agendamento | `END` |
| `dispatch_tools` | `route_after_tools` (código) | Ainda há trabalho no turno | `call_model` |
| `require_authentication` | Lambda constante do grafo | Sempre | `END` |

Os limites são retornados pelos próprios nós como estado terminal; não existe
um nó `limit_reached` separado. A lista de nós e arestas extraída do objeto
compilado está em [`arquitetura.md`](./arquitetura.md).

## Estado, leitores, escritores e reducers

`SchedulingState` é um `TypedDict`. O CLI cria os valores iniciais e o grafo
usa `MemorySaver` com `thread_id=conversation_id`. Nenhum campo declara reducer
LangGraph: a atualização padrão substitui o valor do campo. Quando um nó
acrescenta mensagens/resultados, ele copia a lista, inclui os itens e devolve
a lista completa. Não há ramos paralelos nem escritas concorrentes.

| Campo | Escritores | Leitores | Reducer |
|---|---|---|---|
| `messages` | CLI, `call_model`, `dispatch_tools`, `request_approval`, erros em `revalidate_availability` | `call_model`, `dispatch_tools`, `request_approval`, CLI | Substituição; alguns nós concatenam manualmente |
| `conversation_id` | CLI | `actions.approved_action_key`; CLI usa como `thread_id` | Substituição |
| `round_count` | CLI reinicia por turno; `call_model` incrementa | `route_after_tools` | Substituição |
| `pending_action` | `call_model`, edição/rejeição em `request_approval`, `dispatch_tools`, `revalidate_availability` | Roteamento, `request_approval`, `dispatch_tools`, `revalidate_availability`, CLI | Substituição |
| `pending_message` | `call_model`; `dispatch_tools` e `request_approval` limpam | `dispatch_tools`, `request_approval` | Substituição |
| `approval_result` | `request_approval`; CLI e `dispatch_tools` limpam | Roteamento, `dispatch_tools`, CLI | Substituição |
| `tool_results` | CLI inicia/limpa; `dispatch_tools` acrescenta | `call_model`, `dispatch_tools`, `booking_result_response` | Substituição; `dispatch_tools` concatena manualmente |
| `structured_response` | `call_model`, `dispatch_tools`, respostas terminais | `route_after_tools` | Substituição |
| `answer` | `call_model`, `dispatch_tools`, `request_approval`, `require_authentication`, `revalidate_availability` | CLI | Substituição |
| `authenticated_user` | CLI após `/login` | `call_model`, roteamento, `execute_tool_calls` | Substituição |
| `approval_decision` | `request_approval`; `dispatch_tools` limpa | `route_after_approval` | Substituição |
| `proposal_version` | `call_model` ao propor agendamento; `request_approval` ao editar | `call_model`, `request_approval` | Substituição |
| `approved_action_key` | `request_approval` ao aprovar; `dispatch_tools` e erros limpam | `dispatch_tools` | Substituição |
| `completed_actions` | `dispatch_tools` | `dispatch_tools` | Substituição; cópia e atualização manual |
| `approval_expires_at` | `call_model` ao propor; `actions` ao aprovar, editar ou encerrar | `actions.request_appointment_approval` | Substituição |
| `professional_name` | `validate_professional`; `call_model` e `actions` limpam ao trocar a proposta | `request_approval`, `actions`, CLI lê o payload do interrupt | Substituição |
| `professional_validated` | `validate_professional`; `call_model` e `actions` limpam ao trocar a proposta | Roteamento, `request_approval` | Substituição |
| `execution_deadline` | CLI inicia por turno | Nós que verificam limite; `ApiClient` recebe o mesmo deadline | Substituição |
| `workflow_step_count` | Nós via `_budget_update`; CLI reinicia por turno | `_limit_reason` | Substituição |
| `external_call_count` | Nós via `_budget_update`; CLI reinicia por turno | `_limit_reason`, `dispatch_tools` | Substituição |
| `total_model_tokens` | `call_model`; CLI reinicia por turno | `call_model`, `_limit_reason` | Substituição |
| `tool_call_counts` | `call_model`; CLI reinicia por turno | `call_model` | Substituição; o nó copia e atualiza manualmente |
| `termination_reason` | Nós e `actions`; CLI define `user_exit` ou limpa por turno | Roteamento | Substituição |
| `error_class` | Nós de erro; CLI limpa por turno | Consumidor do estado final | Substituição |

`agent_session_cookie` e `user_session_cookie` pertencem ao `ApiClient`, não
ao `SchedulingState`. O `thread_id` também é metadado de configuração do
checkpointer, não um campo do estado.

## Padrões e limites conhecidos

| Padrão | Uso no grafo atual | Por que este nível | Padrões não usados |
|---|---|---|---|
| Agente com ferramentas e laço limitado | `call_model` pode responder ou solicitar ferramenta; `dispatch_tools` retorna ao modelo enquanto o turno não termina | A mensagem livre pode combinar pedido, preferência e esclarecimento; uma regra fixa não classifica todas as formulações. O laço é limitado por orçamento e ferramentas declaradas | Planejamento aberto não é usado porque as operações são administrativas e as escritas exigem confirmação |
| Workflow sequencial com portão humano | `validate_professional` → `request_approval` → `revalidate_availability` → `dispatch_tools` | A escrita só deve ocorrer depois de aprovação explícita e nova validação da disponibilidade | Não há escrita automática nem aprovação inferida pelo modelo |
| Roteamento condicional em código | `route_from_start`, `route_after_model`, `route_after_approval` e `route_after_tools` | As condições são verificáveis no estado (autenticação, aprovação, erro, orçamento); código é o nível mais simples e previsível | Roteamento por embedding ou por julgamento do modelo não é usado para essas condições |
| Paralelização, orquestrador-trabalhador e avaliador-otimizador | Não usados | O protótipo tem um único Atendente e não tem tarefas independentes que exijam ramos concorrentes ou ciclos de crítica | Gestor/Secretária são papéis futuros, não trabalhadores implementados |

### Estado acumulado e reducers

O grafo não executa nós em paralelo, portanto não há atualizações concorrentes
que precisem de reducer do LangGraph. `messages` e `tool_results` são listas;
as funções do CLI e de `dispatch_tools` criam uma nova lista e acrescentam os
itens na ordem sequencial de execução. Os demais campos são substituições de
estado (um valor por vez), conforme a tabela acima. Assim, a demonstração de
sobrescrita entre ramos paralelos não se aplica à topologia implementada; se
forem adicionados nós paralelos, essa conclusão deixará de valer para os campos
compartilhados atualizados por mais de um ramo.

### Parâmetro de framework

O CLI declara `recursion_limit=32` ao invocar o grafo, embora o fluxo também
tenha limites de domínio próprios (`MAX_WORKFLOW_STEPS=8` e
`MAX_EXTERNAL_CALLS=10`). Como o limite é passado explicitamente, uma mudança
do padrão do LangGraph não altera esse teto. Uma atualização da biblioteca ainda
pode mudar a semântica interna do limite; por isso a versão está fixada em
`requirements.txt` e o grafo deve ser inspecionado e reavaliado após atualização.

- **Agente com ferramentas e loop limitado:** escolhido porque a mensagem
  livre pode pedir uma consulta ou um agendamento; o modelo propõe resposta ou
  tool call, e o código valida e executa apenas as ferramentas declaradas. Os
  limites impedem chamadas sem controle.
- **Workflow sequencial com aprovação humana:** usado porque a gravação altera
  a agenda; a proposta pausa antes da escrita, o código valida o profissional
  e revalida o horário após a aprovação.
- **Roteamento determinístico em código:** autenticação, aprovação,
  revalidação, término e erro dependem do estado e de regras de segurança; o
  modelo não escolhe esses destinos.
- **Sem paralelismo:** cada transição executa um único nó. Não há reducers de
  agregação nem agentes Gestor/Secretária ou nó RAG dedicado no grafo atual.
  O modelo pode chamar `consultar_politica` pelo nó `dispatch_tools`; a
  ferramenta usa o índice vetorial local e não contém políticas oficiais.
- **Orçamento por turno:** 8 etapas, 10 chamadas externas, 6.000 tokens
  reportados, 120 segundos; até 1.000 tokens por resposta e timeout de até 30
  segundos por chamada. O CLI também configura `recursion_limit=32`.
- **Término e erro:** o estado distingue conclusão normal, saída do usuário,
  limite, ação rejeitada, aprovação expirada, loop improdutivo, erro
  recuperável e erro fatal; a classe de erro é `recoverable` ou `fatal`.
- **Detecção de repetição:** uma tool call de leitura idêntica é identificada
  pelo hash de nome e argumentos; `MAX_IDENTICAL_TOOL_CALLS=1` encerra o fluxo
  antes de executar a repetição.
- **Aprovação e idempotência:** a aprovação expira após 120 segundos. A chave
  identifica conversa, ferramenta e argumentos canônicos; `completed_actions`
  evita repetir a escrita no checkpoint em memória. Não há persistência entre
  reinícios nem proteção para a janela entre a escrita externa e o checkpoint.
