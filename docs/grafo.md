# Grafo do agente

> O fluxo de agendamento já usa `StateGraph` e LangGraph checkpointing em
> memória. Os nós de RAG e Gestor continuam como proposta até serem implementados.

## 1. O que roda hoje

`src/agent/app.py::run_scheduling_flow` mantém a conversa em uma lista `messages`
durante o processo. A cada rodada, envia as mensagens e as ferramentas ao LLM.
O terminal inicia em modo convidado e aceita `/login`, `/help` e `/sair`.
Uma sessão técnica separada autentica as chamadas do agente à API; os dados da
conta do usuário autenticado ficam em estado separado e nunca são enviados ao
LLM como texto ou credencial. O login identifica o usuário para operações de
agendamento, mas não filtra a consulta de agendamentos por paciente.
Se o modelo pedir uma ferramenta, o código a executa, acrescenta o resultado à
conversa e chama o modelo novamente. Se não pedir ferramenta, mostra a resposta
e, no modo interativo, aguarda outra mensagem do paciente.

```text
START
  → criar sessão na API
  → receber mensagem do paciente
  → chamar LLM com histórico e ferramentas
      ├─ sem tool call → mostrar resposta
      │    ├─ modo não interativo → END
      │    ├─ paciente encerra/EOF → END
      │    └─ nova mensagem → chamar LLM
      └─ com tool call → despachar ferramenta
           ├─ consultar_disponibilidade → consultar API → acrescentar retorno → chamar LLM
           ├─ confirmar_agendamento → criar agendamento na API → acrescentar retorno → chamar LLM
           └─ ferramenta desconhecida → erro
  → depois de 5 rodadas de ferramentas → resposta de limite → END
```

O código repete chamadas ao LLM quando recebe `RateLimitError`, até cinco
tentativas, com espera exponencial iniciada em cinco segundos. Erros HTTP do
LLM, de conexão ou da API terminam a execução com erro. Não há limite total de
tempo ou tokens declarado no código.

### Nós e decisões atuais

| Etapa/nó lógico | O que faz | Chama LLM? | Quem decide o próximo passo | Estado observado |
|---|---|---:|---|---|
| `abrir_sessao_tecnica` | Autentica a conta própria do agente na API e guarda o cookie técnico no `ApiClient` | Não | Código | `agent_session_cookie` no cliente |
| `login_usuario` | `/login` autentica a conta do usuário no terminal e guarda apenas sua identidade local | Não | Pessoa fornece e-mail/senha; código valida a resposta da API | `authenticated_user` no estado |
| `receber_mensagem` | Lê a mensagem inicial ou a próxima mensagem interativa | Não | Pessoa fornece a próxima entrada; código encerra por comando/EOF | Texto local |
| `consultar_llm` | Envia histórico e definições de ferramentas | Sim | Modelo escolhe resposta ou tool call | Lista `messages` |
| `consultar_disponibilidade` | Consulta agendamentos na API; pode resolver identificador de paciente | Não | Código despacha a função pedida pelo modelo | Retorno da API em `messages` |
| `confirmar_agendamento` | Envia os argumentos recebidos para criar agendamento na API | Não | Código despacha a função pedida pelo modelo | Retorno da API em `messages` |
| `responder_ou_limitar` | Mostra resposta final ou informa que o limite de rodadas foi atingido | Não | Código | Texto da resposta |

As arestas para as duas ferramentas são escolhidas pelo modelo a partir das
tool calls. Antes de `confirmar_agendamento`, o nó `request_approval` usa
`interrupt`, associado ao `thread_id` da conversa e ao checkpointer em memória.
A aprovação, rejeição ou edição é retomada por `Command(resume=...)`. Após
aprovação, o grafo reconsulta a disponibilidade antes do despacho da escrita.
Ver os pontos de aprovação e o fluxo esperado em [`humano.md`](./humano.md).

## 2. Grafo proposto para LangGraph

O diagrama abaixo é um alvo para implementação, não uma descrição do código
atual. Os pontos `interrupt` devem ocorrer antes de qualquer efeito externo.

```text
START
  → receber_mensagem
  → chamar_modelo
      ├─ resposta sem ferramenta → validar_saida → responder →
      │    ├─ continuar conversa → receber_mensagem
      │    └─ encerrar → END
      ├─ tool call de consulta → validar_argumentos
      │    → consultar_disponibilidade → anexar_resultado → chamar_modelo
      └─ tool call de escrita → validar_argumentos
           → preparar_proposta
           → interrupt: paciente/gestor confirma, rejeita ou edita
                ├─ rejeita → responder_sem_escrita → END/continuar
                ├─ edita → validar_edicao → preparar_proposta → interrupt
                └─ aprova → revalidar_dados_e_permissão
                     → aplicar_escrita_idempotente → anexar_resultado
                     → chamar_modelo

Fluxo de publicação de política (ingestão, antes de uso no RAG):
  receber_documento → validar_metadados → interrupt: responsável aprova?
      ├─ rejeita → manter_fora_do_índice → END
      └─ aprova → indexar_versão_aprovada → END
```

O Gestor usa o mesmo padrão de aprovação para criação, atualização e remoção
de recursos: apresentar recurso e argumentos exatos, pausar, validar a
resposta, e só então executar a operação autorizada. Os tipos de recurso e a
semântica de remoção ainda precisam ser definidos com a clínica.

## 3. Padrões e autonomia

| Padrão | Onde se aplica | Justificativa inicial | Quando não usar |
|---|---|---|---|
| Agente com ferramentas/laço limitado | Interpretação de texto livre e escolha entre consultar, propor ou responder | O modelo pode precisar escolher uma ferramenta conforme a intenção; o laço tem teto de rodadas | Se regras determinísticas cobrirem as rotas, preferir router/workflow em código |
| Sequencial com portão | Confirmação humana antes de gravar agendamento ou alterar recurso | A escrita só prossegue depois de aprovação para argumentos específicos | Não é necessário para consulta somente leitura |
| Router | Separar os fluxos de agendamento, orientação, documento/RAG e gestão | Permite encaminhar tarefas a nós especializados com rotas limitadas | Se houver uma única tarefa e nenhuma escolha de rota |

Esta justificativa ainda é preliminar. Com o grafo implementado, registrar no
diagrama qual decisão concreta depende do modelo. Para cada aresta condicional,
indicar se decide uma regra em código, uma busca por embedding ou o modelo.
Quando o modelo escolher uma rota, restringir a saída às rotas válidas por
schema e validar em código.

## 4. Estado do grafo

No código atual, o histórico é uma lista `messages` em memória e o cookie da
API fica no `ApiClient`. Não há estado tipado de LangGraph, reducer,
checkpointer ou persistência entre processos.

Tabela a completar quando o estado do grafo for implementado:

| Campo | Tipo | Quem escreve | Quem lê | Origem | Reducer/justificativa |
|---|---|---|---|---|---|
| `messages` | Lista de mensagens | Nós de conversa e ferramentas | Nó do LLM | Paciente, modelo e ferramentas | A definir; preservar ordem das mensagens |
| `conversation_id` / `thread_id` | Identificador | Entrada/controlador | Checkpointer e nós de retomada | Metadado da conversa | Não acumulado |
| `tool_rounds` | Inteiro | Código | Roteamento/limite | Contador da execução | Atualização determinística |
| `pending_action` | Objeto de proposta | Nó que prepara escrita | Nó de aprovação e retomada | Tool call validada | Sobrescrita controlada; uma ação pendente por thread, se essa for a decisão |
| `approval_result` | Objeto/status | Retomada humana | Nó de validação | Resposta da pessoa | Não deve misturar aprovações de ações diferentes |
| `tool_results` | Lista de resultados | Nós de ferramenta | Nó do LLM/verificador | API/RAG | Definir reducer se houver ramos paralelos |

Separar mensagens conversacionais do estado operacional. Identificadores,
contadores, estado da aprovação e resultados validados devem ser campos
explícitos. Não copiar conteúdo clínico para o estado sem necessidade. Se
houver vários agentes, documentar o contrato mínimo que cada um recebe e
devolve.

Não há paralelismo no fluxo atual, portanto não há reducer concorrente a
justificar nem demonstração de sobrescrita entre ramos. Se o grafo passar a ter
ramos paralelos que acumulam resultados, definir o reducer de cada campo e
registrar uma execução comparando o resultado com e sem esse reducer.

## 5. Limites, término e erros

| Limite/saída | Situação atual | Decisão necessária para o grafo |
|---|---|---|
| Rodadas de tool call | `MAX_TOOL_ROUNDS = 5` | Manter como parâmetro explícito e definir saída segura ao atingir o teto |
| Tentativas por rate limit | `MAX_LLM_RETRIES = 5` | Preservar no desenho e documentar erros fatais versus repetíveis |
| Espera entre tentativas | `RETRY_BACKOFF_SECONDS = 5`, exponencial | Definir teto total de espera/tempo da execução |
| Tokens e duração total | Sem teto no código | Definir e aplicar limites explícitos |
| Pausa humana sem resposta | Não implementada | Definir prazo; expirar ou encaminhar sem aprovar automaticamente |
| Erro da API | Vira `RuntimeError` | Modelar como estado/saída recuperável ou fatal, conforme erro |
| Repetição de escrita | Sem chave de idempotência no fluxo do agente | Derivar chave da ação aprovada e evitar duplicidade |

O término deve distinguir ao menos: resposta concluída, usuário encerrou,
recusa/insuficiência, limite atingido, ação rejeitada, aprovação expirada,
erro recuperável e erro fatal. `MAX_TOOL_ROUNDS` limita iterações; não é, por
si só, detector de laço improdutivo.

## 6. Conferência entre desenho e implementação

O grafo de agendamento é compilado em
`src/agent/workflows/scheduling.py::build_scheduling_graph` com
`MemorySaver`. O CLI fornece um `thread_id` estável por conversa e envia
`Command(resume=...)` para retomar uma proposta interrompida.

O comportamento de confirmação, edição, rejeição, expiração e repetição deve
ser conferido com execuções registradas em `logs/`; detalhes dos responsáveis e
dos pontos de aprovação estão em [`humano.md`](./humano.md).
