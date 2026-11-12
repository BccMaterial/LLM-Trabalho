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

O material do case descreve a organização atual da fila como arbitrária, mas não informa qual ferramenta a equipe usa hoje, quem define a ordem, quanto tempo leva um atendimento, nem o tempo médio de espera. Não vamos inventar esses números. Antes de apresentar uma comparação de impacto, a clínica deve registrar a linha de base: duração do atendimento administrativo, espera por avaliação, cancelamentos e desistências, com período e denominador definidos.

Também faltam políticas oficiais para calcular prioridade, cancelar ou remarcar, e para determinar quais documentos são obrigatórios além do encaminhamento. Até essas regras serem aprovadas pela clínica, o agente deve expor a insuficiência da informação e encaminhar a decisão a uma pessoa autorizada. O sistema não usará simulações de exames nem estimará prazo de diagnóstico.

### Regras de domínio já documentadas

- A clínica tem capacidade limitada e não pode aumentar a quantidade de exames disponíveis no curto prazo.
- Um paciente pode realizar de quatro a seis exames, dependendo do caso.
- O encaminhamento médico é necessário para realizar os exames.
- O horário deve respeitar a disponibilidade real consultada na API e a preferência informada pelo paciente.
- Se o horário pedido não estiver disponível, o paciente deve receber opções reais ou ser convidado a escolher outra faixa.
- Um agendamento só é gravado depois da confirmação explícita do paciente.

## 3. Finalidade e limites

O sistema apoia o atendimento administrativo de pacientes e responsáveis, a organização operacional da fila e da agenda e a conferência de pendências documentais. Ele não realiza diagnóstico, não recomenda tratamento e não deduz gravidade clínica a partir de texto livre. A priorização só pode usar critérios formalizados e aprovados pela clínica; sem esses critérios, o gestor prepara os dados e solicita revisão humana.

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

**Meta do protótipo, ainda não medida:** 100% das gravações devem ter confirmação explícita e corresponder a um horário que a API indicava como disponível no momento da gravação. Denominador: total de tentativas de gravação no conjunto de avaliação. A concordância da prioridade com a referência aprovada deve ser medida separadamente antes de se definir uma meta clínica; não há referência rotulada no repositório.

Os casos de avaliação devem usar dados autorizados e minimizados, com identificadores removidos ou pseudonimizados. Nenhum caso clínico real será incluído no repositório. Até a clínica fornecer dados e política aprovados, os casos descritos em `docs/io.md` são cenários de fluxo, não resultados de avaliação.

## 8. Dados e risco

Suspeita diagnóstica, laudos, histórico e encaminhamento podem conter dados de saúde sensíveis. A API deve fornecer somente os campos necessários a cada tarefa. O histórico clínico não deve ser copiado integralmente para prompts, logs ou memória conversacional. Logs devem registrar identificadores técnicos, decisão, fonte, versão da regra e resultado da ferramenta; conteúdo clínico só pode ser retido conforme política institucional aprovada.

**Maior risco:** priorização incorreta, exposição de dados de saúde ou gravação indevida de um horário. **Plano B:** bloquear escrita quando a confirmação, a regra ou a fonte estiver ausente; manter cancelamentos e exceções em estado pendente; encaminhar para pessoa autorizada; permitir interrupção e revisão humana; auditar a decisão sem registrar dados clínicos desnecessários.

## 9. Estado de implementação

O repositório tem uma API Flask com recursos de profissionais e um protótipo de agente que envia uma mensagem fixa ao modelo. Ainda não há integração de agendamentos, ferramenta de priorização, secretária digital, verificador, laço conversacional ou benchmark executado. A arquitetura deste documento é o desenho-alvo, não uma descrição do que já está funcionando.
