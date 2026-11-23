# Observabilidade do agente

## Perguntas e decisões

| Perspectiva | Pergunta respondida pelos traces | Decisão apoiada |
| --- | --- | --- |
| Negócio | Qual foi a categoria da saída e quais fontes foram usadas? | Revisar o fluxo e priorizar ajustes de produto sem usar o trace para inferir diagnóstico. |
| Operação | O modelo ou uma ferramenta falhou, e qual foi o motivo de término? | Investigar indisponibilidade, corrigir integração ou orientar uma nova tentativa. |
| Pagador | Quantos tokens de entrada e saída foram usados por chamada e versão? | Estimar consumo e comparar versões; os traces não são uma fatura. |
| Responsável pelo sistema | Qual versão, ferramenta, referência de política e decisão de aprovação participaram? | Reconstruir a execução, avaliar uma mudança e decidir por correção ou rollback. |

## Estrutura e atributos

Cada chamada ao grafo produz um span raiz `invoke_agent`. Chamadas repetidas ao
modelo e às ferramentas são filhas do span da execução:

```text
invoke_agent
├── chat
├── execute_tool
├── chat
└── execute_tool
```

Uma retomada de aprovação é uma nova invocação raiz, relacionada à mesma
conversa apenas pelo checkpoint interno do LangGraph; o identificador da
conversa não é exportado. O span raiz registra modo e turno, versão do sistema,
motivo de término, classe de erro, uso total de tokens, nomes das ferramentas,
versão/decisão da aprovação e categorias da saída (status, ação, suficiência e
tipos de fonte). Quando há política recuperada, registra somente documento,
versão e trecho.

`chat` usa os atributos semânticos GenAI `gen_ai.operation.name`,
`gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` e
`gen_ai.response.finish_reasons`. `execute_tool` registra o nome semântico da
ferramenta, sucesso/falha e, para busca de política, a contagem e referências
minimizadas.

Nenhum span recebe prompts, mensagens do paciente, conteúdo recuperado,
argumentos ou resultados completos das ferramentas, identificadores de
pacientes/agendamentos, referências livres da saída, credenciais ou texto de
exceção. Falhas registram somente tipo de exceção e status do span.

## Falhas e sinais

1. **Falha de conexão/limite do modelo.** O span `chat` fica com status `ERROR`
   e `error.type`; a raiz indica `recoverable_error` e a classe da falha.
2. **Falha de rede da API durante consulta ou revalidação.** O fluxo captura a
   exceção e responde de forma segura, sem expor detalhes técnicos. Esse é um
   modo silencioso para quem opera: o sinal fica no span `execute_tool` com
   status `ERROR`/`error.type` e na raiz com motivo/classe de término e
   categoria de saída `consulta_indisponivel` ou `informacao_insuficiente`.
3. **Resposta do modelo rejeitada pelo contrato.** A conversa pode continuar
   com uma mensagem segura sem uma exceção visível ao operador. Esse segundo
   modo silencioso aparece na raiz como `recoverable_error`, com saída
   `informacao_insuficiente`; o span `chat` pode ter sucesso, pois a falha está
   na validação posterior.
4. **Busca de política sem trecho aplicável.** Não é falha de transporte: o
   span `execute_tool` indica sucesso e zero referências; a raiz registra
   suficiência `insuficiente`. Isso permite distinguir ausência de evidência
   de indisponibilidade do índice.
5. **Coletor Jaeger indisponível.** A exportação pode falhar sem interromper o
   atendimento; traces não entregues não estarão consultáveis. Verifique se o
   serviço `jaeger` está ativo e se o endpoint OTLP está acessível.

## Destino, acesso e retenção

No desenvolvimento, o agente exporta OTLP/gRPC para Jaeger em
`http://localhost:4317`; a interface de consulta fica em
`http://localhost:16686`. Os ports do Compose são vinculados a `127.0.0.1`.
Use somente dados sintéticos nesse destino local.

Jaeger all-in-one usa armazenamento em memória por padrão: os traces se perdem
ao reiniciar o serviço e não há prazo de retenção durável configurado. Também
não foi identificada uma política institucional de acesso, retenção ou descarte
para traces. Portanto, o destino é apenas para desenvolvimento local; antes de
qualquer uso com dados reais, a instituição precisa definir responsável,
perfis de acesso, prazo de retenção, descarte e um backend protegido. A
interface local não tem autenticação.

`OTEL_EXPORTER_OTLP_ENDPOINT` pode substituir o endpoint local. O nome do
serviço é `llm-trabalho-agent`; na interface Jaeger, selecione-o, filtre pela
operação `invoke_agent` e pela janela de tempo da execução, então abra o trace
para consultar spans e atributos.
