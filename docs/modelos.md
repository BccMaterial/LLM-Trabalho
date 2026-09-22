# Escolha de modelos

Será utilizado um desses três modelos:
- Mistral Small 4
- Llama 4 Scout
- Qwen3 30B A3B

# Critérios de escolha dos modelos

Abaixo estão os critérios que serão utilizados para a escolha do modelo.

## Tool calling

O tool calling é um requisito importante para os agentes deste projeto, pois permite a utilização de ferramentas externas para executar tarefas específicas, com o modelo sendo capaz de identificar quando precisa utilizar uma ferramenta.

Portanto, modelos sem suporte adequado a **function calling/tool calling** não atendem ao requisito principal da arquitetura de agentes.

## Saída estruturada

Além de gerar texto, o modelo precisa produzir informações que possam ser processadas pelo sistema.

Por exemplo, uma solicitação de agendamento poderia gerar:

```json
{
  "acao": "agendar_consulta",
  "paciente_id": "123",
  "tipo_consulta": "avaliacao",
  "data": "2026-10-10",
  "horario": "14:00"
}
```

## Janela de contexto

O modelo deve suportar o volume de informações necessário para as conversas e para os dados apresentados ao agente.

Para este projeto, a necessidade de contexto deverá ser determinada a partir de:
- histórico da conversa;
- informações administrativas;
- dados necessários para a consulta;
- resultados da simulação;
- instruções do agente;
- schemas das ferramentas.

### Custo

O custo será calculado considerando os tokens de entrada e saída.

A fórmula utilizada será:
```text
custo por chamada =
(tokens de entrada × preço de entrada +
 tokens de saída × preço de saída) / 1.000.000
```

Como os agentes podem realizar várias chamadas para concluir uma única tarefa, o custo da trajetória completa deverá considerar todas as chamadas:
```text
custo por execução =
custo de uma chamada × número de chamadas
```

Essa consideração é especialmente importante neste projeto porque uma única interação pode envolver o usuário, tool callings e as respostas do modelo.

## Política de dados

A aplicação trabalha com informações relacionadas a pacientes e, portanto, a política de dados é um requisito de arquitetura.

Antes de utilizar uma API pública com dados reais, será necessário verificar:
- Política de retenção dos dados;
- Utilização dos dados para treinamento;
- Local de processamento;
- Possibilidade de utilizar informações anonimizadas;
- Requisitos legais e institucionais;
- Possibilidade de hospedagem própria.

A escolha do provedor não deverá ser baseada apenas no preço.

## Modelos candidatos

Foram selecionados três candidatos de famílias diferentes para comparação.

### Mistral Small 4

O Mistral Small 4 é um modelo híbrido que reúne capacidades de instrução, raciocínio e programação, além de suporte multimodal.

A documentação atual informa:
- Contexto de **256k tokens**;
- Suporte a function calling;
- Suporte a structured outputs;
- Suporte a agentes;
- Preço de **US$ 0,15 por milhão de tokens de entrada**;
- Preço de **US$ 0,60 por milhão de tokens de saída**;
- Licença Apache 2.0 para os pesos.

Esse candidato é particularmente relevante porque o projeto já utiliza a família Mistral durante o desenvolvimento e porque a documentação disponibiliza suporte às funcionalidades necessárias para agentes.

### Llama 4 Scout

O Llama 4 Scout é um modelo multimodal da família Llama, baseado em arquitetura Mixture-of-Experts.

Para comparação de API, pode ser utilizado por meio de um serviço que ofereça o modelo, como o Workers AI.

Nesse ambiente, a documentação informa:
- Contexto de **131.000 tokens**;
- Function calling;
- Visão;
- Preço de aproximadamente **US$ 0,27 por milhão de tokens de entrada**;
- Preço de aproximadamente **US$ 0,85 por milhão de tokens de saída**.

A Meta também disponibiliza os modelos Llama para utilização direta ou por meio de parceiros e serviços de nuvem.

### Qwen3 30B A3B

Como terceiro candidato, será considerado o Qwen3 30B A3B.

Uma possibilidade de execução para o benchmark é utilizar uma infraestrutura que disponibilize esse modelo por API, como o Workers AI.

Na tabela atual de preços desse serviço, o modelo aparece com aproximadamente:
- US$ 0,051 por milhão de tokens de entrada;
- US$ 0,335 por milhão de tokens de saída.

O uso de um modelo Qwen também permite avaliar uma alternativa de arquitetura diferente da Mistral e da Llama, mantendo o foco nos mesmos requisitos de agente.

## Comparação inicial

Os valores abaixo representam as informações disponíveis no momento da elaboração deste documento e deverão ser registrados com a data da consulta, pois preços e versões de modelos podem mudar.

| Eixo              | Mistral Small 4         | Llama 4 Scout                 | Qwen3 30B A3B                         |
| ----------------- | ----------------------- | ----------------------------- | ------------------------------------- |
| Contexto          | 256k                    | 131k                          | verificar na infraestrutura escolhida |
| Tool calling      | Sim                     | Sim                           | validar no endpoint escolhido         |
| Structured output | Sim                     | validar no endpoint escolhido | validar no endpoint escolhido         |
| Multimodalidade   | Sim                     | Sim                           | não é requisito principal             |
| Raciocínio        | Sim                     | disponível na família         | validar no endpoint                   |
| Execução          | API / pesos disponíveis | API/parceiros / pesos         | API / infraestrutura compatível       |
| Entrada           | US$ 0,15/M              | US$ 0,27/M*                   | US$ 0,051/M*                          |
| Saída             | US$ 0,60/M              | US$ 0,85/M*                   | US$ 0,335/M*                          |
| Benchmark próprio | Necessário              | Necessário                    | Necessário                            |

Valores referentes à infraestrutura utilizada para a comparação, e não necessariamente ao preço de todos os provedores que disponibilizam o modelo.

A tabela não determina o modelo escolhido. Ela apenas estabelece os candidatos que deverão ser submetidos ao mesmo experimento.

A própria aula recomenda não utilizar somente rankings públicos para decidir um modelo. O benchmark deve representar as tarefas reais do projeto.

## Benchmark próprio

Será realizado um benchmark com cinco tarefas representativas do sistema.

Todos os modelos deverão receber:
- O mesmo prompt;
- As mesmas instruções;
- Os mesmos dados;
- Os mesmos schemas;
- A mesma configuração sempre que suportada;
- O mesmo número de execuções.

A comparação não deverá alterar o prompt para favorecer um modelo.

### Caso 1 — Informações sobre avaliação

**Entrada:**

> "Gostaria de saber como funciona o processo de avaliação neuropsicológica para uma pessoa com suspeita de TEA."

Será analisado:
- clareza da resposta;
- respeito ao escopo administrativo/informativo;
- ausência de diagnóstico;
- capacidade de seguir as instruções.

### Caso 2 — Agendamento

**Entrada:**

> "Gostaria de marcar uma avaliação para a próxima semana."

O modelo deverá identificar que é necessário utilizar a ferramenta de agenda.

Será analisado:

- se identificou corretamente a necessidade de tool calling;
- nome da ferramenta;
- argumentos gerados;
- formato da chamada;
- necessidade de solicitar informações que ainda não foram fornecidas.

### Caso 3 — Remarcação

**Entrada:**

> "Preciso remarcar minha avaliação."

Será utilizado um schema de ferramenta para verificar se o modelo consegue estruturar corretamente a solicitação.

Serão observados:
- identificação da ação;
- identificação das informações faltantes;
- chamada da ferramenta;
- validade do JSON;
- consistência dos argumentos.

### Caso 4 — Simulação de aumento da demanda

**Entrada:**

> "Simule o que aconteceria com o tempo médio de espera se a quantidade de novos pacientes aumentasse 30%."

O modelo deverá interpretar a solicitação e utilizar a ferramenta de simulação.

Será observado:
- compreensão dos parâmetros;
- chamada correta da ferramenta;
- interpretação dos resultados;
- explicação do resultado para o usuário.

### Caso 5 — Análise gerencial

**Entrada:**

> "O tempo médio de espera aumentou. Quais informações devemos analisar para entender o motivo?"

O modelo deverá produzir uma resposta estruturada e, quando apropriado, utilizar as ferramentas disponíveis.

Serão observados:

* identificação dos indicadores relevantes;
* utilização correta das ferramentas;
* coerência da análise;
* formato da resposta.

## Tabela de resultados do benchmark

Após executar os cinco casos, os resultados deverão ser registrados em uma tabela como a seguinte:

| Caso | Modelo          | Tool calling | JSON válido | Resposta adequada | Tokens entrada | Tokens saída | Latência mediana |
| ---- | --------------- | ------------ | ----------- | ----------------- | -------------: | -----------: | ---------------: |
| 1    | Mistral Small 4 | —            | —           | preencher         |      preencher |    preencher |        preencher |
| 1    | Llama 4 Scout   | —            | —           | preencher         |      preencher |    preencher |        preencher |
| 1    | Qwen3 30B A3B   | —            | —           | preencher         |      preencher |    preencher |        preencher |
| 2    | Mistral Small 4 | preencher    | preencher   | preencher         |      preencher |    preencher |        preencher |
| 2    | Llama 4 Scout   | preencher    | preencher   | preencher         |      preencher |    preencher |        preencher |
| 2    | Qwen3 30B A3B   | preencher    | preencher   | preencher         |      preencher |    preencher |        preencher |
| ...  | ...             | ...          | ...         | ...               |            ... |          ... |              ... |

Os cinco casos não constituem uma avaliação estatística completa. O objetivo inicial é verificar o comportamento dos candidatos nas tarefas específicas do projeto antes da escolha definitiva.

A aula recomenda justamente um benchmark próprio de tarefas reais do domínio para substituir uma decisão baseada apenas em leaderboard.

---

## Estimativa de custo

Para cada modelo será registrado o número médio de tokens utilizado por chamada.

A fórmula será:

```text
Custo =
(Tokens_in × Preço_in +
 Tokens_out × Preço_out) / 1.000.000
```

Considerando `N` chamadas por execução:

```text
Custo da execução =
Custo de uma chamada × N
```

Para 100 execuções:

```text
Custo_100 =
Custo da execução × 100
```

Para uma estimativa mensal:

```text
Custo_mensal =
Custo da execução × número de execuções mensais
```

Como exemplo de estrutura de cálculo:

| Modelo          | Tokens entrada/chamada | Tokens saída/chamada | Chamadas/execução | Custo/execução | Custo/100 execuções |
| --------------- | ---------------------: | -------------------: | ----------------: | -------------: | ------------------: |
| Mistral Small 4 |                  medir |                medir |             medir |       calcular |            calcular |
| Llama 4 Scout   |                  medir |                medir |             medir |       calcular |            calcular |
| Qwen3 30B A3B   |                  medir |                medir |             medir |       calcular |            calcular |

Os preços devem ser atualizados antes da entrega final do trabalho.

## Matriz de decisão

A decisão será baseada nos sete eixos apresentados na aula:

| Eixo         | Pergunta                                                              |
| ------------ | --------------------------------------------------------------------- |
| Qualidade    | O modelo atende às cinco tarefas do benchmark?                        |
| Custo        | Qual é o custo por execução e por mês?                                |
| Latência     | O TTFT e o tempo total são aceitáveis?                                |
| Contexto     | A janela suporta o maior contexto necessário?                         |
| Formato      | O modelo suporta JSON Schema e ferramentas?                           |
| Dados        | A política do provedor permite o uso pretendido?                      |
| Estabilidade | A versão pode ser fixada e possui política de manutenção/depreciação? |

O limiar mínimo de qualidade deverá ser definido **antes de analisar os resultados**, evitando escolher o critério depois de observar qual modelo apresentou melhor resultado.

## Modelo escolhido

A escolha definitiva será feita após a execução do benchmark.

O critério será selecionar o modelo que:
1. atenda aos requisitos funcionais dos agentes;
2. apresente comportamento adequado nas tarefas do benchmark;
3. suporte tool calling e saída estruturada de maneira confiável;
4. apresente custo compatível com o volume estimado;
5. apresente latência aceitável;
6. seja compatível com a política de dados definida para o projeto.

Neste momento, dentre os 3 modelos, ainda estamos decidindo qual será o modelo escolhido para a arquitetura de agentes.

## Possibilidade de roteamento entre modelos

A arquitetura não precisa obrigatoriamente utilizar um único modelo para todas as tarefas.

Caso o benchmark demonstre que um modelo menor atende às tarefas simples, enquanto outro apresenta vantagens nas tarefas mais complexas, pode ser utilizado **roteamento de modelos**.

Um possível fluxo seria:

```text
                 Solicitação
                      |
                      v
              Modelo principal
                      |
             +--------+--------+
             |                 |
        tarefa simples     tarefa complexa
             |                 |
             v                 v
        resposta          modelo de maior
                            capacidade
```

Outra possibilidade é utilizar validação:

```text
LLM
 |
 v
JSON Schema
 |
 +---- válido ------> executar ferramenta
 |
 +---- inválido ----> nova tentativa
                         |
                         v
                    outro modelo
                         |
                         v
                   humano, se necessário
```

Essa possibilidade é particularmente relevante para um sistema de agentes, pois diferentes tarefas podem apresentar diferentes níveis de dificuldade.

## Condições para reconsiderar o modelo

A escolha do modelo não será permanente.

O modelo poderá ser reconsiderado quando ocorrer uma das seguintes situações:
- lançamento de uma nova versão relevante;
- alteração significativa de preço;
- aumento do custo por execução;
- aumento da latência;
- falhas recorrentes no tool calling;
- falhas na saída estruturada;
- alteração da política de dados;
- descontinuação ou depreciação da versão utilizada;
- aumento da complexidade dos agentes;
- alteração do volume de usuários;
- surgimento de um modelo que atenda aos requisitos com menor custo ou menor latência.

Quando houver uma mudança relevante, os mesmos cinco casos do benchmark deverão ser executados novamente para permitir uma comparação reprodutível.
