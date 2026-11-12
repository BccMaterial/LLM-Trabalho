# Seleção e avaliação de modelos

## Estado da decisão

Este documento define como comparar candidatos para o desenho Atendente/Gestor/Secretária. A comparação ainda não foi executada; não há modelo escolhido, medições de custo/latência ou resultado de benchmark no repositório. O código exige `LLM_MODEL` no ambiente para não usar silenciosamente um modelo fora da lista de candidatos.

Não declarar um vencedor com base apenas em rankings, especificações publicadas ou preço nominal. As informações de cada endpoint e os preços devem ser conferidos na data da execução, pois variam por provedor e podem mudar.

## Candidatos

| Candidato | Por que comparar | O que precisa ser validado no endpoint selecionado |
|---|---|---|
| Mistral Small 4 | Família já considerada no protótipo do grupo | Tool calling, schema estruturado, português, latência, preço, retenção e política de dados |
| Llama 4 Scout | Alternativa de família e provedores | Tool calling, schema estruturado, português, latência, preço, retenção e política de dados |
| Qwen3 30B A3B | Terceira família para comparação | Tool calling, schema estruturado, português, latência, preço, retenção e política de dados |

O nome do modelo não basta para tornar endpoints comparáveis: registrar provedor, versão exata, região e configuração. Não enviar dados reais até a clínica aprovar o tratamento de dados e o provedor.

## Critérios

1. **Uso correto de ferramentas:** escolher consulta ou escrita apropriada e gerar argumentos válidos.
2. **Saída estruturada:** produzir o schema de `docs/io.md` e respeitar status permitidos.
3. **Grounding:** responder só com a API/política retornada e indicar fonte/suficiência.
4. **Segurança operacional:** não gravar sem confirmação; não inventar disponibilidade, prioridades ou política.
5. **Tratamento de ambiguidade e erro:** solicitar dado faltante, detectar contradição, parar quando a fonte/API for insuficiente e encaminhar à pessoa autorizada.
6. **Português e latência:** avaliar clareza para paciente e latência total da trajetória, incluindo ferramentas.
7. **Privacidade e custo:** verificar retenção/uso dos dados e calcular custo a partir dos tokens e das tarifas do endpoint efetivamente usado.

## Casos do benchmark

Cada caso deve usar o mesmo prompt versionado, schema, contexto, retorno de ferramentas, orçamento e número de repetições para todos os candidatos. A avaliação de agendamento/prioridade precisa de registros autorizados, minimizados e uma referência aprovada; sem isso, o caso não é executado e não recebe nota.

| Caso | Entrada | Comportamento esperado | Evidência |
|---|---|---|---|
| 1. Orientação administrativa | Pergunta sobre encaminhamento ou procedimento | Consultar política vigente, responder em português com fonte, ou dizer que não encontrou regra | Prompt, trecho/política recuperada, resposta e verificador |
| 2. Agendamento | Pedido de horário com identidade e preferência | Consultar cadastro, encaminhamento e disponibilidade; sugerir somente slots retornados; aguardar confirmação antes da escrita | Tool calls, argumentos, retorno da API, confirmação e resultado |
| 3. Informação incompleta/contraditória | Pedido sem campo essencial ou com divergência entre mensagem e cadastro | Perguntar ou encaminhar; não assumir valor | Estado, pergunta gerada, fonte da divergência e status |
| 4. Cancelamento/remarcação | Pedido para cancelar ou alterar horário | Consultar regra vigente; se ausente, registrar pendência sem alterar a agenda | Política consultada, ação pendente e ausência de escrita de cancelamento |
| 5. Gestor/Secretária | Pedido para revisar conflito ou documento pendente | Usar API/checklist autorizado, retornar alerta/pendência estruturado; não inferir clínica | Fonte, tarefa do agente, resultado do verificador e encaminhamento |

Não há ferramenta de simulação de exames nem estimativa de prazo de diagnóstico. As entradas não devem conter casos ou números inventados como se fossem pacientes reais.

## Protocolo de execução

Antes de rodar:

- aprovar a política de prioridade e a referência de avaliação com a clínica;
- preparar casos autorizados e minimizados; registrar sua origem e versão sem armazenar dados identificáveis no repositório;
- configurar o endpoint e preços atuais;
- escolher o mesmo prompt versionado (`prompts/*_v1.txt`), schema e parâmetros para cada candidato;
- fixar o orçamento e repetir cada caso com quantidade igual de execuções.

Por execução, guardar `run_id`, data, caso, provedor/modelo/versão, versão/hash do prompt, parâmetros, chamadas de ferramenta e argumentos, validações, resultado, fonte, suficiência, tokens de entrada/saída, latência, custo e ocorrência de escalonamento. Remover conteúdo pessoal dos logs; nunca incluir laudos ou segredos.

### Quatro execuções de integração com logs

Para cumprir a entrega de execução, registrar ao menos quatro trajetórias completas em `logs/`, cobrindo: caminho feliz com confirmação, informação incompleta, erro/insuficiência de fonte e encaminhamento para revisão humana. Cada log deve permitir reconstruir etapas e ferramentas sem expor dado sensível. No estado atual, esses logs ainda não existem.

## Cálculo de custo

Registrar preços oficiais do endpoint na data da execução. Para cada chamada `j`:

```text
custo_j = (tokens_entrada_j × preço_entrada_por_milhão
         + tokens_saída_j × preço_saída_por_milhão) / 1.000.000
custo_execução = soma(custo_j para todas as chamadas de modelo da trajetória)
custo_100_execuções = 100 × custo_execução_médio
custo_semestre = custo_execução_médio × interações_por_dia × 182
```

Se houver cache, ferramentas cobradas ou tarifas distintas por modelo/provedor, registrar essas parcelas separadamente. `interações_por_dia` deve vir de volume observado ou meta explicitamente identificada; não está informado ainda. Não preencher estimativas com números supostos.

## Tabela de resultados

| Caso | Candidato/endpoint | Execuções | Tool calls válidas | Schema válido | Decisão correta segundo verificador | Tokens entrada/saída | Latência mediana | Custo médio |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Mistral Small 4 / endpoint a definir | pendente | pendente | pendente | pendente | pendente | pendente | pendente |
| 1 | Llama 4 Scout / endpoint a definir | pendente | pendente | pendente | pendente | pendente | pendente | pendente |
| 1 | Qwen3 30B A3B / endpoint a definir | pendente | pendente | pendente | pendente | pendente | pendente | pendente |
| 2–5 | Todos os candidatos | pendente | pendente | pendente | pendente | pendente | pendente | pendente |

## Regra de decisão

Escolher somente após completar a matriz de avaliação. Um candidato é inelegível se falhar repetidamente em confirmação de escrita, fonte, schema, privacidade ou escalonamento seguro, mesmo que seja mais barato. Entre elegíveis, comparar taxa de decisões corretas no verificador, latência e custo por execução. A decisão deve registrar responsável, evidências e condições de revisão. Até lá, **modelo escolhido: nenhum**.
