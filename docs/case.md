# Case: atendimento e gestão de avaliações neuropsicológicas

## Grupo

- Caio Troiano Collino
- Thiago Pereira Lins da Silva
- Vinícius Vianna Egydio de Carvalho

## 1. Problema

Pacientes encaminhados para avaliações neuropsicológicas e a equipe de recepção enfrentam espera e retrabalho porque a fila e a agenda não têm um processo de priorização e conferência consistente e rastreável.

## 2. Contexto do case

### Situação conhecida

A clínica realiza avaliações neuropsicológicas. A documentação inicial informa que a ordem da fila é arbitrária, que há espera prolongada, reclamações e desistências. A capacidade de atendimento é limitada por profissionais especializados. Um paciente pode realizar de quatro a seis exames, conforme o caso, e precisa de encaminhamento médico, que pode vir de profissional da própria clínica ou de outra clínica.

O paciente ou responsável inicia o contato por mensagem. O sistema interpreta a solicitação, consulta dados autorizados na API da clínica, encaminha tarefas administrativas e apresenta opções compatíveis com a preferência e a disponibilidade retornada pela API. A API é a fonte oficial para cadastro, encaminhamento, fila e agenda.

### Processo atual e lacunas de informação

O material público usado no case descreve a organização atual da fila como arbitrária, mas não informa qual ferramenta a equipe usa hoje, quem define a ordem, quanto tempo leva um atendimento, nem o tempo médio de espera. Esses dados não estão disponíveis e não serão solicitados como condição do trabalho. Não vamos inventar números nem apresentar uma comparação de impacto real.

Não temos políticas oficiais para calcular prioridade, cancelar ou remarcar, nem para determinar quais documentos são obrigatórios além do encaminhamento. O protótipo não depende de obtê-las: seus casos usam regras e registros sintéticos explicitamente identificados; fora deles, o agente deve indicar que a informação falta e não executar a ação. O sistema não usará simulações de exames nem estimará prazo de diagnóstico.

### Regras de domínio já documentadas

- A clínica tem capacidade limitada e não pode aumentar a quantidade de exames disponíveis no curto prazo.
- Um paciente pode realizar de quatro a seis exames, dependendo do caso.
- O encaminhamento médico é necessário para realizar os exames.
- O horário deve respeitar a disponibilidade real consultada na API e a preferência informada pelo paciente.
- Se o horário pedido não estiver disponível, o paciente deve receber opções reais ou ser convidado a escolher outra faixa.
- Um agendamento só é gravado depois da confirmação explícita do paciente.

## 2.5 A justificativa de negócio — a venda

### Por que um agente, e não software comum

O atendimento começa em linguagem livre e pode misturar dúvidas, preferências de agenda, informações faltantes e mudanças de última hora; o agente interpreta o pedido, identifica o que falta e conduz esclarecimentos antes de acionar regras e ferramentas determinísticas. Um formulário ou fluxo fixo cobre campos conhecidos, mas não conduz por si só essa conversa variável; a escrita na agenda, a aplicação de regras e os limites de autonomia continuam sob controle do código e de confirmação humana.

### Ganho esperado para a operação

O ganho esperado é organizar em um fluxo rastreável o atendimento administrativo, as pendências, a fila e os horários, para reduzir desencontros e retrabalho e apoiar melhor o uso do tempo dos profissionais. O sistema também pode ajudar a equipe a lidar com cancelamentos, remarcações e outras mudanças de última hora, apresentando informações e tarefas em um estado claro para revisão humana; não promete aumentar a capacidade clínica nem decide prioridade clínica por conta própria.

Não há linha de base, volume observado, duração de tarefas ou taxa de retrabalho no material disponível. Portanto, não é possível calcular honestamente um ganho de X para Y, uma porcentagem ou economia financeira. Qualquer percentual, inclusive 10%, seria inventado. A hipótese de organização e apoio ao tempo da equipe é qualitativa e não foi testada; este projeto não depende de obter esses dados para concluir seu protótipo acadêmico.

### Ganho esperado para o paciente ou responsável

O benefício esperado para quem procura atendimento é ter uma conversa mais clara, evitar repetir informações já confirmadas, receber orientação administrativa consistente e compreender o que está pendente ou qual é o próximo passo. Isso é uma expectativa de design do fluxo, não uma melhora comprovada de espera, satisfação, acesso ou resultado neuropsicológico.

### Custo, limites e risco da proposta

- **Operação:** o custo real por atendimento não está calculado, pois não há modelo/provedor selecionado, execuções registradas ou volume observado. `docs/modelos.md` descreve como medir tokens, latência e custo quando o benchmark for executado; não apresenta resultados atuais.
- **Construção:** o esforço de desenvolvimento do grupo não foi cronometrado e não é convertido em valor monetário.
- **O que se perde:** respostas ambíguas, indisponibilidade de dados e exceções podem exigir mais interações ou encaminhamento, e uma interpretação inadequada pode confundir o paciente ou gerar trabalho adicional. Por isso, o protótipo não diagnostica, não define prioridade clínica e não executa alterações sem as salvaguardas descritas no case.

**Limite da evidência:** os benefícios operacionais e humanos acima não têm teste no repositório e não podem ser demonstrados por cenários simulados. Os cenários podem verificar apenas o comportamento técnico do protótipo diante de entradas e retornos definidos; não comprovam economia de tempo, melhora da organização real, experiência do paciente ou efeito sobre a qualidade do cuidado. O projeto não afirma ter essa comprovação.

## 3. Finalidade e limites

O sistema foi proposto para apoiar o atendimento administrativo de pacientes e responsáveis, a organização operacional da fila e da agenda e a conferência de pendências documentais. Ele não realiza diagnóstico, não recomenda tratamento e não deduz gravidade clínica a partir de texto livre. Como não temos critérios oficiais de prioridade, esta entrega não calcula nem simula prioridade clínica; o tema fica descrito como limite e não como dependência para concluir o protótipo.

## 4. Usuários e aprovações

| Perfil | Papel no sistema | O que pode fazer | O que não pode delegar ao agente |
|---|---|---|---|
| Paciente ou responsável — usuário principal | Inicia o atendimento por mensagem e recebe opções | Informar preferências, esclarecer dados, confirmar ou recusar uma opção e solicitar cancelamento ou remarcação | Não precisa fornecer novamente dados que a API já confirme; deve poder interromper o atendimento |
| Recepcionista/secretária | Acompanha pendências administrativas e documentos | Consultar tarefas, conferir completude segundo política oficial e pedir documentos faltantes | Validar conteúdo clínico ou inventar regras administrativas |
| Gestor da agenda | Acompanha fila, disponibilidade, conflitos e cancelamentos | Revisar alertas operacionais e encaminhar casos para análise | Alterar prioridades clínicas sem critérios aprovados ou apagar registros |
| Responsável autorizado da clínica | Aprova políticas e exceções de alto impacto | Aprovar critérios de priorização, políticas e decisões encaminhadas | Delegar ao modelo a aprovação de regras ou exceções |

O paciente confirma o próprio agendamento. Um responsável autorizado da clínica aprova as regras de prioridade e qualquer exceção que altere a ordem da fila. Cancelamentos e remarcações seguem uma política oficial ainda a ser fornecida; até lá, o agente apenas registra a solicitação e a encaminha.

## 5. Desenho dos três agentes

| Agente | Responsabilidade | Entradas autorizadas | Saída principal |
|---|---|---|---|
| Atendente | Conversar com paciente/responsável, classificar intenção, coletar o mínimo necessário e apresentar opções | Mensagem atual, identidade autenticada e dados necessários retornados pela API | Pergunta de esclarecimento, orientação administrativa com fonte, opções reais ou confirmação de resultado |
| Gestor | Conferir fila e agenda e aplicar critérios de prioridade aprovados | Registros autorizados da API e versão vigente dos critérios aprovados | Prioridade operacional estruturada, alerta de conflito ou encaminhamento humano, sempre com evidência |
| Secretária | Organizar pendências e conferir completude administrativa de encaminhamentos e documentos | Metadados/documentos autorizados e checklist oficial | Checklist concluído, item faltante ou tarefa para revisão humana |

Um controlador de fluxo, implementado em código, encaminha cada tarefa ao agente adequado e mantém o estado compartilhado. Os agentes não trocam mensagens livres entre si: recebem tarefas com campos definidos e devolvem resultados validados. A prioridade que o case previa continua no papel do gestor.

## 6. Interação principal

- **Canal do protótipo:** mensagem de texto; uma interface de chat é adequada porque o paciente pode começar com pedidos incompletos ou combinar dúvidas e agendamento na mesma mensagem. O canal concreto usado pela clínica ainda precisa ser confirmado.
- **Quem começa:** paciente ou responsável.
- **Trocas esperadas:** de três a oito mensagens do usuário, incluindo esclarecimentos e confirmação; o fluxo pode terminar antes se faltarem dados ou se houver necessidade de atendimento humano. O orçamento técnico é definido em `docs/arquitetura.md`.
- **Formato de saída:** resposta em português e objeto validado com `resultado`, `fonte` e `suficiencia`.
- **Término:** agendamento confirmado; solicitação encaminhada; ausência de cadastro ou encaminhamento válido; falta de disponibilidade; desistência do usuário; limite de execução; ou escalonamento humano.

### Diálogo ilustrativo

Os horários abaixo são marcadores para demonstrar a conversa; em execução, devem ser substituídos somente por opções devolvidas pela API.

**Paciente:** Quero marcar minha avaliação de manhã.  
**Atendente:** Posso verificar. Primeiro vou confirmar seu cadastro e se o encaminhamento está registrado.  
**Atendente:** A agenda retornou [opção A] e [opção B] para o período da manhã. Qual você prefere?  
**Paciente:** A opção A.  
**Atendente:** Confirma que deseja reservar [opção A]?  
**Paciente:** Sim, confirmo.  
**Atendente:** O agendamento foi registrado. Consultei a disponibilidade e confirmei o registro na agenda da clínica.

## 7. Verificação e critério de sucesso

O modelo não verifica a própria resposta. Um verificador determinístico, separado dos prompts, deve validar:

1. se toda opção sugerida veio da disponibilidade atual da API, respeita a preferência e não cria conflito;
2. se a gravação ocorreu somente após confirmação explícita e se o resultado retornado pela API corresponde à opção confirmada;
3. se o resultado de prioridade respeita o schema, a versão da regra aprovada e os dados consultados; se a regra estiver ausente ou os dados forem insuficientes, deve bloquear a decisão e pedir revisão humana;
4. se a resposta identifica fonte e suficiência e não afirma dado ausente.

**Critério técnico no conjunto sintético:** todas as tentativas de escrita devem decorrer de confirmação explícita para a opção exata retornada no caso, e nenhuma resposta pode afirmar sucesso sem retorno de gravação. Denominador: tentativas de escrita nos cenários sintéticos. O benchmark verifica parte disso em mocks. Esse critério não mede impacto na clínica nem efeito humano; não há referência rotulada de prioridade porque a prioridade não faz parte do protótipo executável.

Os casos de avaliação são sintéticos e usam identificadores fictícios; nenhum dado de paciente ou política interna é necessário ou incluído. Os casos em `docs/io.md` e `benchmarks/casos.json` avaliam fluxos e limites do software, não desempenho ou resultado de pessoas reais.

## 8. Dados e risco

Suspeita diagnóstica, laudos, histórico e encaminhamento podem conter dados de saúde sensíveis. A API deve fornecer somente os campos necessários a cada tarefa. O histórico clínico não deve ser copiado integralmente para prompts, logs ou memória conversacional. Logs devem registrar identificadores técnicos, decisão, fonte, versão da regra e resultado da ferramenta; conteúdo clínico só pode ser retido conforme política institucional aprovada.

**Maior risco:** priorização incorreta, exposição de dados de saúde ou gravação indevida de um horário. **Plano B:** bloquear escrita quando a confirmação, a regra ou a fonte estiver ausente; manter cancelamentos e exceções em estado pendente; encaminhar para pessoa autorizada; permitir interrupção e revisão humana; auditar a decisão sem registrar dados clínicos desnecessários.

## 9. Estado de implementação

O repositório contém API Flask com autenticação, usuários, profissionais e operações de agenda; o agente Python usa a biblioteca `openai`, consulta e grava pela API, mantém a conversa em turnos e oferece duas ferramentas. O benchmark separado exercita sete cenários sintéticos com ferramentas simuladas. A agenda de demonstração não representa uma clínica real. Ainda não estão implementados os três agentes especializados, a priorização com regra aprovada, RAG, MCP, LangGraph nem um verificador determinístico completo para proteger as escritas do agente interativo. O benchmark tem verificações automáticas próprias e não substitui esse verificador de aplicação.

## 10. Workflow da entrega 1

1. **Receber a mensagem** do paciente/responsável no chat — o modelo classifica a intenção; o código mantém o turno e limita o laço.
2. **Identificar o dado que falta** — o modelo pergunta quando a mensagem é ambígua; o código exige identidade autenticada antes de revelar registro.
3. **Consultar cadastro/agenda** — o código chama a API por HTTP; a API é fonte dos registros; erros e ausência de registro devem voltar como resultado explícito.
4. **Interpretar o retorno** — o modelo explica opções retornadas ou a insuficiência; o código limita respostas aos dados recebidos e ao contrato de saída.
5. **Lidar com divergência ou ausência de regra** — o modelo pede esclarecimento ou encaminha; não calcula prioridade sem regra aprovada nem inventa política.
6. **Pedir confirmação inequívoca** para a opção exata — o paciente decide; o silêncio, preferência ou ambiguidade não são confirmação.
7. **Gravar somente após confirmação** — escrita pela API; o paciente confirma a ação reversível por procedimento posterior e a equipe pode revisar. A confirmação deve ser validada também em código antes da chamada da ferramenta.
8. **Informar resultado e encerrar** — resposta em português com fonte e suficiência; o código encerra por sucesso, encaminhamento, erro persistente, desistência ou limite.

As decisões em linguagem livre e a interpretação de contradições justificam o uso restrito do modelo. Identidade, autorização, limites, validação da disponibilidade, confirmação de escrita e término pertencem ao código. A versão interativa ainda precisa tornar o estado e o bloqueio de escrita mais explícitos; os casos do benchmark já verificam parte desse contrato em ambiente simulado.

## 11. Sistema, autonomia e fronteiras

O sistema recebe texto, consulta a API da aplicação por HTTP, prepara uma resposta estruturada e, no caso de agendamento, pode gravar após confirmação. Nesta primeira entrega há um agente Atendente; Gestor e Secretária são papéis futuros da mesma arquitetura, não agentes já executáveis. A autonomia é de **agente com workflow sequencial limitado**: um FAQ não consegue resolver pedidos em linguagem natural com dados incompletos, consultar informação atual nem conduzir uma confirmação em turnos; planejamento aberto e decisão clínica não são autorizados.

| Ferramenta | Ação | Leitura/escrita | Reversível? | Integração |
|---|---|---|---|---|
| `consultar_disponibilidade` | Consultar agendamentos do paciente | Leitura | Sim, sem alterar estado | HTTP `GET /api/appointments` na API Flask; hoje lista registros existentes, não calcula horários livres |
| `confirmar_agendamento` | Registrar a opção informada | Escrita | Alteração posterior segue operação separada; deve requerer confirmação explícita | HTTP `POST /api/appointments` na API Flask; falta uma barreira determinística no agente antes da escrita |

Essa API própria é software tradicional separado do processo do agente. A demonstração usa registros de exemplo e não se conecta à clínica nem à agenda real. O nome da ferramenta de consulta sugere disponibilidade, mas a API atual não oferece esse dado; por isso as opções de disponibilidade nos casos do benchmark são fixtures locais, e não saída real dessa integração.

## 12. Justificativa de negócio e limites da evidência

O valor esperado é ajudar a equipe a manter pedidos, pendências e opções de agenda organizados; reduzir repetição de informação para pacientes/responsáveis; e responder com clareza quando há conflito ou mudança de última hora. A hipótese é melhorar a organização do processo como um todo e a experiência humana, sem prometer ganho clínico, diagnóstico ou aumento de capacidade.

O agente é adequado apenas para a parte em que a mensagem pode vir incompleta, misturar pedidos ou contradizer o registro, exigindo esclarecimento em tempo de execução e consulta a uma fonte atual. Um formulário e regras fixas resolvem campos conhecidos, mas não conduzem por si só essa conversa; o agente permanece limitado a interpretar e redigir, enquanto código e API autorizam e executam operações.

Não há contato, observação do processo ou dados operacionais da clínica disponíveis ao grupo. Portanto não existe linha de base, volume ou denominador defensável para calcular redução percentual, tempo economizado, produtividade ou retorno financeiro. Não atribuímos um percentual hipotético — inclusive 10% — porque pareceria resultado medido sem evidência. A justificativa é uma hipótese qualitativa de organização e experiência a ser discutida, não uma alegação comprovada nem dependente de obter acesso da clínica para concluir o protótipo. Os casos artificiais avaliam regras do software, não efeitos sobre pessoas. Um número de impacto real exigiria estudo autorizado com medidas humanas adequadas, e está fora do que estes dados permitem afirmar.

O custo de inferência observado e a conta por 100 casos estão em [`docs/modelos.md`](modelos.md); custo semestral não é estimado porque não há volume diário. O custo de desenvolvimento é o trabalho acadêmico do grupo e não foi convertido em dinheiro. O principal custo de erro é uma informação administrativa incorreta ou uma gravação indevida; por isso o protótipo não deve ser apresentado como serviço clínico, e a confirmação/escrita precisa de barreira determinística antes de qualquer uso real.

## 13. Verificador, dados e expansão

Para esta etapa, o benchmark versiona casos, fontes, ferramentas simuladas, orçamento e validações estruturais. Os sete casos atuais incluem resposta sem política, paciente inexistente, divergência com encaminhamento, consulta de horário, ausência de confirmação, escrita após confirmação e cancelamento sem política. O caso que não deve disparar a ação principal é a preferência ainda não confirmada; todos os exemplos usam identificadores e registros fictícios. O verificador de benchmark não comprova correção humana ou de clínica.

Para as etapas seguintes, a proposta é: RAG apenas sobre políticas sintéticas/publicamente disponíveis para exercitar recuperação, deixando claro que não são regras da clínica; MCP como fronteira de serviço para a API local de agenda; LangGraph para representar e comparar o workflow com estado explícito; e, na Parte 3, separar Atendente, Gestor e Secretária quando houver tarefas realmente distintas. Nenhuma dessas propostas presume acesso futuro à clínica. O maior risco é o modelo transformar ausência/contradição de informação em certeza e iniciar uma escrita incorreta; o plano B é bloquear a ferramenta em código, apresentar a insuficiência e terminar em revisão humana.
