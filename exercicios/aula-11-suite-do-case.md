# Suíte de cases - Testes

## 1. O dataset, com origem declarada

O arquivo [`dataset-agendamento.yaml`](./dataset-agendamento.yaml) traz os casos de teste que serão utilizados para validar o comportamento do assistente virtual. Ele contém uma lista de casos, cada um com uma descrição, entrada e saída esperada.

O arquivo [`dataset-priorizacao.yaml`](./dataset-priorizacao.yaml) traz os casos de teste que serão utilizados para validar o comportamento do agente de priorização. Ele contém uma lista de casos, cada um com uma descrição, entrada e saída esperada.

## 2. Os níveis, escolhidos com justificativa

Os dois agentes atuam sobre o fluxo real de priorização e agendamento. Por isso,
a avaliação não deve olhar apenas para a resposta final: também deve conferir o
uso das ferramentas e o estado dos agendamentos após a execução. As falhas mais
custosas são priorizar incorretamente um paciente, marcar um horário sem
confirmação ou informar ao paciente que houve um agendamento quando ele não foi
registrado.

| Nível | Propriedade esperada | Avaliação esperada | O que é falhar no nosso domínio |
|---|---|---|---|
| Determinístico | A resposta do agente de priorização contém `coeficiente_priorizacao` numérico entre 0 e 1. | Validar o schema da saída e conferir `0 <= coeficiente_priorizacao <= 1`. | Retornar `1.2`, um texto no lugar do número ou omitir o coeficiente. |
| Determinístico | Os horários enviados para registro têm início anterior ao fim e datas válidas. | Validar o formato de data/hora e comparar os instantes de início e fim. | Tentar marcar um exame das 10h às 10h ou com data inválida. |
| Determinístico | A mensagem ao paciente não contém métricas internas do simulador. | Conferir a saída contra os campos internos, como taxa de ocupação, tempo ocioso e coeficiente de priorização. | Informar ao paciente a taxa de ocupação ou o coeficiente calculado. |
| Trajetória | O agente de priorização consulta o simulador com a suspeita e o estado atual dos agendamentos antes de calcular o coeficiente. | Inspecionar o trace: `simular_estado_clinica` deve ocorrer uma vez, com ambos os dados, antes da resposta estruturada. | Retornar um coeficiente sem simular ou chamar a ferramenta sem incluir a suspeita ou os agendamentos atuais. |
| Trajetória | O agente de agendamento usa a simulação antes de escolher quais horários oferecer. | Inspecionar o trace para verificar a chamada ao simulador antes da seleção/apresentação das opções. | Sugerir horários sem consultar o simulador, ou exibir suas métricas diretamente ao paciente. |
| Trajetória | Uma solicitação para horário específico consulta a API de disponibilidade antes de tentar agendar. | No trace, verificar `consultar_disponibilidade_agenda` antes de `agendar_exames`; se indisponível, não deve haver chamada de agendamento. | Tentar reservar sem verificar disponibilidade ou chamar a ferramenta de agendamento depois de a API informar que o horário está ocupado. |
| Trajetória | O agente só chama a ferramenta de agendamento após confirmação clara do paciente. | Verificar no trace que a confirmação precede `agendar_exames`. | Registrar uma opção apenas porque o paciente disse que ela “pode funcionar”, sem confirmar. |
| Resultado | Os horários confirmados ficam registrados uma única vez para o paciente correto. | Consultar o estado persistido após a execução e comparar quantidade, paciente e intervalos com o esperado. | Informar sucesso sem registro, duplicar um exame ou gravá-lo para outro paciente. |
| Resultado | Uma opção não confirmada ou indisponível não altera os agendamentos. | Comparar o estado antes e depois da execução; não deve surgir novo registro. | Criar um agendamento enquanto o paciente ainda está escolhendo ou após retorno de indisponibilidade. |
| Juiz LLM | A justificativa da priorização é coerente com a suspeita recebida e com as métricas retornadas pelo simulador, sem afirmar diagnóstico. | Aplicar rubrica binária: aceita se relacionar os dados fornecidos ao coeficiente sem diagnosticar; rejeita se inventar dados, contradizer as métricas ou declarar diagnóstico. | A justificativa afirma um diagnóstico ou diz que a ocupação é baixa quando o simulador retornou ocupação alta. |
| Juiz LLM | A resposta ao paciente é clara, útil e informa opções ou o próximo passo. | Aplicar rubrica binária para clareza e utilidade; validar separadamente, de forma determinística, que a resposta não contém métricas internas do simulador. | Oferecer horários sem indicar como o paciente pode escolher; ou revelar taxa de ocupação, tempo ocioso ou coeficiente — este último caso também falha na checagem determinística. |

O nível determinístico cobre contratos e limites que não exigem interpretação.
Trajetória é necessária porque uma resposta aparentemente correta pode ter sido
produzida sem consultar o simulador, sem validar disponibilidade ou sem aguardar
confirmação. Resultado verifica o efeito real das ferramentas, e não apenas a
afirmação do agente. As propriedades de comunicação e coerência da justificativa
exigem julgamento contextual; serão avaliadas com rubricas explícitas e juiz
validado, conforme o tópico 3 do enunciado. A qualidade do tom não será usada
para compensar falhas nos níveis de trajetória ou resultado.

## 3. O juiz, e como ele vai ser validado

### Propriedades escolhidas

O juiz terá duas rubricas independentes, uma por agente:

1. **Agente de priorização:** avaliar se a justificativa é coerente com a
   suspeita recebida e com as métricas retornadas pelo simulador, sem inventar
   informações nem afirmar um diagnóstico. O juiz não substitui a regra de
   priorização nem decide se o coeficiente numérico está correto; formato e
   limites do coeficiente são verificados deterministicamente.
2. **Agente de agendamento:** avaliar se a mensagem ao paciente é clara, útil e
   indica as opções disponíveis ou a ação esperada do paciente. O juiz não
   avalia chamadas de ferramentas, disponibilidade real, sequência de
   confirmação nem exposição literal de métricas do simulador: esses aspectos
   são cobertos por verificações determinísticas ou de trajetória na seção 2.

### Rubricas binárias

#### Agente de priorização — coerência da justificativa

**SIM — justificativa aceita** quando a resposta:

- se apoia na suspeita e nos dados efetivamente fornecidos;
- representa corretamente as métricas do simulador quando as menciona;
- explica a relação entre esses elementos e a prioridade indicada, sem
  apresentar hipótese como diagnóstico;
- não acrescenta histórico, sintomas ou fatos que não estejam na entrada.

**NÃO — justificativa rejeitada** quando a resposta:

- contradiz ou inventa dado da suspeita, do histórico ou da simulação;
- afirma ou insinua um diagnóstico clínico como fato;
- não oferece uma justificativa relacionada aos dados, ou dá uma explicação
  incompatível com a prioridade descrita.

**Exemplo SIM — caso_015 de `dataset-priorizacao.yaml`:**

> “Piora recente relatada e alta ocupação com pouco tempo ocioso indicam
> prioridade elevada.”

A justificativa usa a piora descrita e as métricas retornadas (ocupação de
0,95 e duas horas ociosas), sem declarar diagnóstico.

**Exemplo NÃO — mesma entrada e métricas:**

> “O paciente tem Alzheimer confirmado; a ocupação é baixa, então não há
> necessidade de prioridade.”

A resposta inventa um diagnóstico e contradiz a taxa de ocupação alta.

#### Agente de agendamento — clareza e utilidade

**SIM — resposta aceita** quando a mensagem:

- comunica de forma direta as opções ou o resultado relevante ao pedido;
- deixa claro o que o paciente pode fazer em seguida, como escolher uma opção
  ou indicar outro horário;
- não afirma que um agendamento foi concluído se a entrada não informa sucesso
  da ferramenta.

**NÃO — resposta rejeitada** quando a mensagem:

- é vaga ou não deixa claro quais opções existem nem qual é o próximo passo;
- não responde ao pedido de agendamento ou confunde sugestão com confirmação;
- afirma que um horário foi reservado sem retorno de sucesso da ferramenta.

**Exemplo SIM — caso_022 de `dataset-agendamento.yaml`:**

> “Posso oferecer 03/12, das 9h às 10h, ou 04/12, das 14h às 15h. Qual opção
> prefere?”

A mensagem lista as opções e pede uma escolha explícita, sem sugerir que já
foram marcadas.

**Exemplo NÃO — mesmo contexto:**

> “A agenda está sendo organizada. Pode deixar.”

A resposta não informa as opções nem diz o que o paciente deve fazer para
prosseguir.

Se a mensagem revelar taxa de ocupação, tempo ocioso ou coeficiente, ela falha
na verificação determinística de confidencialidade definida na seção 2,
independentemente da nota do juiz para clareza.

### Validação do juiz

Antes de adotar as rubricas, serão selecionadas **30 saídas**: 15 justificativas
do agente de priorização, cobrindo diferentes classes de ocupação e casos com
e sem piora relatada, e 15 respostas do agente de agendamento, cobrindo oferta
de horários, confirmação, indisponibilidade e falha de ferramenta. A amostra
deve incluir saídas adequadas e inadequadas para cada rubrica.

Duas pessoas rotularão cada saída independentemente e sem ver o julgamento do
juiz: um integrante do grupo e um revisor com experiência pertinente ao
comportamento avaliado. Para priorização, o revisor deverá ter experiência em
avaliação neuropsicológica; para agendamento, experiência em atendimento ou
rotinas administrativas de clínica. Divergências serão resolvidas pelo revisor
da área, que produzirá o rótulo de referência e registrará o motivo.

Cada rubrica será adotada somente se alcançar **pelo menos 85% de concordância**
com os rótulos de referência na sua amostra: no mínimo **13 de 15** saídas
corretas para cada agente (26 de 30 no total). Abaixo do limiar em qualquer uma
das rubricas, ela não será usada para avaliar a suíte; suas instruções deverão
ser revistas e uma nova amostra rotulada antes de nova tentativa. O limiar e a
divisão da amostra foram definidos antes da validação.

### Viés considerado

O principal risco é o **viés de verbosidade**: uma explicação longa pode soar
mais convincente mesmo quando inventa dados ou não sustenta a prioridade; no
agendamento, uma mensagem prolixa pode parecer mais útil sem orientar o
paciente. Para reduzi-lo, as rubricas verificam critérios observáveis e não
premiam extensão, tom ou eloquência. As entradas, métricas e respostas serão
apresentadas ao juiz em formato fixo, sem incluir o rótulo esperado ou
identificadores de classe. Sempre que possível, será usado para juiz um modelo
diferente daquele que gerou a resposta; em qualquer caso, a adoção dependerá
da concordância separada com os rótulos humanos para cada agente.
