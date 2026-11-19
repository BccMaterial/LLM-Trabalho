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
| `call_model` | Envia histórico e ferramentas ao LLM; valida a resposta final e guarda tool calls pendentes | O modelo escolhe responder ou solicitar uma ferramenta; o código atualiza `messages`, `pending_action`, `pending_message`, `round_count` e `proposal_version` |
| `dispatch_tools` | Executa as tool calls pendentes e anexa os resultados; impede repetir uma ação de agendamento já concluída neste thread | O código exige `approval_result=True` para executar `confirmar_agendamento`; lê e atualiza `tool_results` e `completed_action_keys` |
| `request_approval` | Valida o profissional ativo e pede aprovação para os argumentos exatos da proposta | `actions.request_appointment_approval` chama `interrupt`; o código registra `approval_result`, `approval_decision` e `approved_action_key` ao retomar |
| `revalidate_availability` | Consulta novamente a disponibilidade depois da aprovação | O código mantém ou limpa `pending_action`; o próximo roteamento decide se despacha a escrita |
| `require_authentication` | Informa que é necessário usar `/login` para agendar | O código encerra esse turno sem executar a escrita |
| `limit_reached` | Devolve uma resposta estruturada ao atingir `MAX_TOOL_ROUNDS` | O código encerra o grafo com a resposta de limite |

O CLI mantém o loop de conversa fora do grafo: recebe uma mensagem, invoca o
grafo e imprime a resposta. Para uma proposta interrompida, retoma com
`Command(resume=...)` usando o mesmo `thread_id`.

## Arestas e decisões de roteamento

Todas as bifurcações condicionais abaixo são decididas por funções/lambdas em
Python, exceto a escolha inicial do modelo entre resposta e tool call. Não há
roteamento por embedding.

| Origem | Quem decide | Condição | Destino |
|---|---|---|---|
| `START` | `route_from_start` (código) | Existe `pending_action` e `approval_result` ainda é `None` | `request_approval` |
| `START` | `route_from_start` (código) | Caso contrário | `call_model` |
| `call_model` | Modelo escolhe; `route_after_model` (código) valida o destino | Não há tool call | `END` |
| `call_model` | Modelo escolhe; `route_after_model` (código) valida autenticação | Tool call é `confirmar_agendamento`, sem `authenticated_user` | `require_authentication` |
| `call_model` | Modelo escolhe; `route_after_model` (código) verifica a identidade | Tool call é `confirmar_agendamento`, com usuário autenticado | `request_approval` |
| `call_model` | Modelo escolhe; `route_after_model` (código) identifica a ferramenta | Outra tool call | `dispatch_tools` |
| `request_approval` | Decisão gravada por `actions.request_appointment_approval`; lambda do grafo encaminha | `approval_result is True` | `revalidate_availability` |
| `request_approval` | A mesma decisão e lambda | `approval_result is None` e `approval_decision is None` (edição ou resposta inválida) | `request_approval` |
| `request_approval` | A mesma decisão e lambda | Rejeição ou outra decisão terminal | `END` |
| `revalidate_availability` | Lambda do grafo (código) | `pending_action` continua definida | `dispatch_tools` |
| `revalidate_availability` | Lambda do grafo (código) | A proposta foi invalidada ou a revalidação falhou | `END` |
| `dispatch_tools` | `route_after_tools` (código) | Resposta tem status final de agendamento | `END` |
| `dispatch_tools` | `route_after_tools` (código) | `round_count >= MAX_TOOL_ROUNDS` | `limit_reached` |
| `dispatch_tools` | `route_after_tools` (código) | Caso contrário | `call_model` |
| `require_authentication` | Lambda constante do grafo | Sempre | `END` |
| `limit_reached` | Aresta direta | Sempre | `END` |

O diagrama ASCII e a lista de arestas gerada pelo script estão em
[`arquitetura.md`](./arquitetura.md). O script deriva nos, arestas e o marcador
de condicionalidade do grafo compilado; as condições de cada ramo estão
explicadas na tabela acima.

## Estado, leitores, escritores e reducers

`SchedulingState` é um `TypedDict`. O CLI cria os valores iniciais e o grafo
usa `MemorySaver` com `thread_id=conversation_id`. Nenhum campo declara reducer
LangGraph: a atualização padrão substitui o valor do campo. Quando um nó
acrescenta mensagens/resultados, ele copia a lista, inclui os itens e devolve
a lista completa. Como não há ramos paralelos, não há escrita concorrente nem
reducer de agregação.

| Campo | Escritores | Leitores | Reducer |
|---|---|---|---|
| `messages` | CLI, `call_model`, `dispatch_tools`, `request_approval` e falhas em `revalidate_availability` | `call_model`, `dispatch_tools`, `request_approval`, CLI | Substituição; nós concatenam manualmente |
| `conversation_id` | CLI | `actions.approved_action_key`; CLI usa como `thread_id` | Substituição |
| `round_count` | CLI reinicia por turno; `call_model` incrementa | `route_after_tools` | Substituição |
| `pending_action` | `call_model`, edição/rejeição em `request_approval`, `dispatch_tools`, `revalidate_availability` | Roteamento, `request_approval`, `dispatch_tools`, `revalidate_availability`, CLI | Substituição |
| `pending_message` | `call_model`; nós de ferramentas/aprovação limpam | `dispatch_tools`, `request_approval` | Substituição |
| `approval_result` | `request_approval`; CLI limpa quando não há ação pendente; `dispatch_tools` limpa após executar | Roteamento, `dispatch_tools`, CLI | Substituição |
| `tool_results` | CLI inicia/limpa; `dispatch_tools` acrescenta | `call_model`, `dispatch_tools`, `booking_result_response` | Substituição; `dispatch_tools` concatena manualmente |
| `structured_response` | `call_model`, `dispatch_tools`, `request_approval`, `revalidate_availability`, `limit_reached` | `route_after_tools` | Substituição |
| `answer` | `call_model`, `dispatch_tools`, `request_approval`, `limit_reached` e `revalidate_availability` | CLI | Substituição |
| `authenticated_user` | CLI após `/login` | `call_model`, `execute_tool_calls` | Substituição |
| `approval_decision` | `request_approval`; `dispatch_tools` limpa | Aresta condicional de `request_approval`, roteamento | Substituição |
| `proposal_version` | `call_model` ao propor agendamento; `request_approval` ao editar | `call_model`, `request_approval` | Substituição |
| `approved_action_key` | `request_approval` ao aprovar; `dispatch_tools` e falhas limpam | `dispatch_tools` | Substituição |
| `completed_action_keys` | `dispatch_tools` | `dispatch_tools` | Substituição; cópia e acréscimo manual |

`agent_session_cookie` e `user_session_cookie` pertencem ao `ApiClient`, não
ao `SchedulingState`. O `thread_id` também é metadado de configuração do
checkpointer, não um campo do estado.

## Padrões e limites conhecidos

- **Agente com ferramentas e loop limitado:** o modelo pode responder ou
  escolher entre as ferramentas declaradas. O codigo valida e executa as
  chamadas, e `MAX_TOOL_ROUNDS` limita a continuacao do loop.
- **Workflow sequencial com aprovacao humana:** a criacao de agendamento pausa
  antes da escrita. Depois da aprovacao, o codigo revalida a disponibilidade e
  so entao executa a ferramenta.
- **Roteamento determinístico em código:** autenticação, aprovação, revalidação,
  status final e limite são avaliados pelo estado; o modelo não escolhe esses
  destinos.
- **Estado sem reducers customizados:** não há `Annotated` ou reducer
  registrado no `SchedulingState`; cada atualização substitui o valor anterior.
- **Checkpoint em memória:** `MemorySaver` permite retomar no mesmo processo,
  mas não garante persistência após reinício.
- **Sem paralelismo:** cada transição executa um único nó; Gestor, Secretária,
  ingestão de políticas e RAG continuam fora do grafo implementado.
- **Pontos pendentes:** não há prazo de expiração da aprovação nem limites
  totais de tokens/duração. A idempotência de `completed_action_keys` depende
  do checkpoint em memória e não cobre reinícios ou a janela entre uma escrita
  externa e o checkpoint.
