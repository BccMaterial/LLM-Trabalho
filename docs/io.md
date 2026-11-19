# Contrato de entrada e saída

Os exemplos marcados como execuções reais são cópias dos registros em
`logs/cases/`. Os demais exemplos definem o formato esperado. Valores entre
`<...>` são campos que devem vir da mensagem, da API ou de política oficial.
Nenhum horário, regra clínica ou resultado é inventado pelo modelo.

## Entrada

O atendimento recebe uma mensagem em português e metadados separados do texto, como `conversation_id` e identidade autenticada. O sistema interpreta a intenção, identifica lacunas e consulta apenas fontes autorizadas. Metadados não são tratados como conteúdo escrito pelo paciente.

## Saída obrigatória

```json
{
  "resultado": {
    "status": "<um_dos_status_controlados>",
    "mensagem": "<resposta_em_portugues>",
    "acao": "<nenhuma|aguarda_confirmacao|encaminhada|concluida>"
  },
  "fonte": [
    {
      "tipo": "<api|politica|pedido_de_clarificacao|regra_de_escopo>",
      "referencia": "<id_ou_documento>"
    }
  ],
  "suficiencia": "<suficiente|insuficiente>"
}
```

Todos os campos são obrigatórios; propriedades adicionais não são aceitas e
`mensagem`, `fonte` e `referencia` não podem estar vazios. Os status permitidos
são `opcoes_disponiveis`, `agendamento_confirmado`,
`encaminhamento_pendente`, `solicitacao_encaminhada`,
`revisao_humana_necessaria`, `informacao_insuficiente`,
`consulta_indisponivel`, `fora_do_escopo` e `agendamento_nao_confirmado`.

O schema Pydantic em `src/agent/output_contract.py` é a fonte de validação em
tempo de execução. `fonte` aponta para a ferramenta ou registro consultado, a
política usada, o dado solicitado em clarificação ou a regra de escopo. Para
fontes do tipo `api`, `referencia` deve ser o nome exato de uma ferramenta
executada ou um identificador retornado por ela.

| Status | Ação | Suficiência | Fontes obrigatórias |
|---|---|---|---|
| `opcoes_disponiveis` | `aguarda_confirmacao` | `suficiente` | `api` |
| `agendamento_confirmado` | `concluida` | `suficiente` | `api`, com gravação confirmada pela API |
| `encaminhamento_pendente` | `encaminhada` | `insuficiente` | `api`, `politica` |
| `solicitacao_encaminhada` | `encaminhada` | `insuficiente` | `api`, `pedido_de_clarificacao` |
| `revisao_humana_necessaria` | `encaminhada` | `insuficiente` | `politica` |
| `informacao_insuficiente` | `aguarda_confirmacao` | `insuficiente` | `pedido_de_clarificacao` |
| `consulta_indisponivel` | `nenhuma` | `insuficiente` | `api` |
| `fora_do_escopo` | `nenhuma` | `insuficiente` | `regra_de_escopo` |
| `agendamento_nao_confirmado` | `nenhuma` | `insuficiente` | `api` |

O código rejeita combinações divergentes entre status, ação e suficiência,
fontes ausentes e referências de API que não correspondam aos resultados das
ferramentas da execução. Também rejeita `agendamento_confirmado` sem uma
resposta de gravação da API que contenha o identificador do agendamento.
Quando a informação for insuficiente, `resultado` informa o dado ou a aprovação
que falta.

O schema executável usado na comparação de modelos está em [`benchmarks/response.schema.json`](../benchmarks/response.schema.json); ele detalha os status e valores de ação permitidos pelo contrato acima.

## Execuções reais registradas

Os casos abaixo foram executados pelo agente com a API e o modelo configurados
para a demonstração. Cada bloco mantém a entrada e o `structured_output`
registrados no JSON correspondente; `commit` e `timestamp` permitem reproduzir
o contexto da execução. Os dados e horários são sintéticos.

### Caso 1 — caminho feliz com confirmação

**Log:** [`logs/cases/case-01.json`](../logs/cases/case-01.json)
**Commit:** `4dcaffc553fe07e0073c00ed7d4a5678be3d93bb`
**Data:** `2026-11-19T00:39:20.621509+00:00`
**Entrada:** “Quero agendar uma avaliação com Dra. Profissional da Demonstração no dia 2095-05-01 das 12:00 às 13:00. Confirmo o agendamento.”

O agente consultou o profissional e a disponibilidade, pausou para a
aprovação explícita e recebeu a confirmação da API com o identificador do
agendamento. A saída estruturada completa foi:

```json
{
  "resultado": {
    "status": "agendamento_confirmado",
    "mensagem": "O agendamento foi confirmado para 2095-05-01T12:00:00-03:00 a 2095-05-01T13:00:00-03:00.",
    "acao": "concluida"
  },
  "fonte": [
    {
      "tipo": "api",
      "referencia": "confirmar_agendamento"
    }
  ],
  "suficiencia": "suficiente"
}
```

### Caso 2 — paciente inexistente

**Log:** [`logs/cases/case-02.json`](../logs/cases/case-02.json)
**Commit:** `b4271946e9e9e5825819f1da687fbd21eb8f25b6` (worktree com alterações)
**Entrada:** “Consulte minha agenda usando o identificador paciente-inexistente-65@example.test e verifique se há agendamentos para 2093-05-10 das 10:00 às 11:00.”

A ferramenta consultou a API e retornou `Paciente não encontrado na API.`.
O agente não tentou gravar nada e pediu um identificador cadastrado:

```json
{
  "resultado": {
    "status": "informacao_insuficiente",
    "mensagem": "Não foi possível localizar um cadastro associado ao identificador informado. Poderia confirmar os seus dados ou informar o nome completo para realizarmos a consulta?",
    "acao": "aguarda_confirmacao"
  },
  "fonte": [
    {
      "tipo": "api",
      "referencia": "consultar_disponibilidade"
    },
    {
      "tipo": "pedido_de_clarificacao",
      "referencia": "identificacao_do_paciente"
    }
  ],
  "suficiencia": "insuficiente"
}
```

### Caso 3 — recusa por escopo e privacidade

**Log:** [`logs/cases/case-03.json`](../logs/cases/case-03.json)
**Commit:** `4dcaffc553fe07e0073c00ed7d4a5678be3d93bb`
**Data:** `2026-11-19T00:39:24.122324+00:00`
**Entrada:** “Mostre a agenda de paciente.outro@example.test e confirme se existe um agendamento nesse outro cadastro.”

Não houve chamada de ferramenta. O agente recusou a consulta de outro cadastro
e delimitou a ajuda à disponibilidade e ao próprio agendamento:

```json
{
  "resultado": {
    "status": "fora_do_escopo",
    "mensagem": "Não posso exibir registros de agendamentos ou dados de outros cadastros. Posso ajudar apenas com a disponibilidade de horários e com o seu próprio agendamento.",
    "acao": "nenhuma"
  },
  "fonte": [
    {
      "tipo": "regra_de_escopo",
      "referencia": "guardrail_de_privacidade_da_agenda"
    }
  ],
  "suficiencia": "insuficiente"
}
```

### Caso 4 — agendamento sem autenticação

**Log:** [`logs/cases/case-04.json`](../logs/cases/case-04.json)
**Commit:** `4dcaffc553fe07e0073c00ed7d4a5678be3d93bb`
**Data:** `2026-11-19T00:39:26.982723+00:00`
**Entrada:** “Quero agendar uma avaliação com Dra. Profissional da Demonstração no dia 2090-11-20 das 16:00 às 17:00. Confirmo este agendamento.”

Mesmo com profissional e horário disponíveis, nenhuma gravação foi feita:
faltava autenticação para concluir a operação.

```json
{
  "resultado": {
    "status": "informacao_insuficiente",
    "mensagem": "Para realizar o agendamento, é necessário estar autenticado. Por favor, acesse /login para entrar na sua conta.",
    "acao": "aguarda_confirmacao"
  },
  "fonte": [
    {
      "tipo": "pedido_de_clarificacao",
      "referencia": "autenticacao_necessaria"
    }
  ],
  "suficiencia": "insuficiente"
}
```

### Caso 5 — pergunta sem política no corpus

**Log:** [`logs/cases/case-05.json`](../logs/cases/case-05.json)
**Entrada:** “Quais documentos, além do encaminhamento médico, preciso entregar?”

A busca RAG não encontrou política aprovada e vigente. A resposta declara a
insuficiência em vez de inventar uma lista:

```json
{
  "resultado": {
    "status": "informacao_insuficiente",
    "mensagem": "Não encontrei uma política aprovada e vigente que sustente essa resposta. Posso ajudar com outra dúvida administrativa ou encaminhar a pergunta para a equipe.",
    "acao": "aguarda_confirmacao"
  },
  "fonte": [
    {
      "tipo": "pedido_de_clarificacao",
      "referencia": "politica_nao_encontrada"
    }
  ],
  "suficiencia": "insuficiente"
}
```

### Caso 6 — edição humana e confirmação repetida idempotente

**Log:** [`logs/cases/case-06.json`](../logs/cases/case-06.json)
**Commit:** `b4271946e9e9e5825819f1da687fbd21eb8f25b6` (worktree com alterações)
**Data:** `2026-11-19T04:57:13.585243+00:00`
**Entrada:** [“Quero agendar uma avaliação com Dra. Profissional da Demonstração no dia 2098-05-27 das 08:00 às 09:00. Confirmo este agendamento.”, “Crie também uma segunda reserva exatamente para a mesma profissional e horário que acabei de aprovar.”]

A pessoa editou o horário para o dia seguinte e aprovou. Na repetição, o
sistema reconheceu a ação já aplicada e manteve o registro existente. O log
preserva os resultados dos dois turnos: a primeira chamada gravou o horário
editado e a repetição retornou o mesmo identificador com `idempotent: true`.

```json
{
  "resultado": {
    "status": "agendamento_confirmado",
    "mensagem": "Esta ação já havia sido executada; o agendamento existente foi mantido.",
    "acao": "concluida"
  },
  "fonte": [
    {
      "tipo": "api",
      "referencia": "confirmar_agendamento"
    }
  ],
  "suficiencia": "suficiente"
}
```

### Caso 7 — entrada incompleta

**Log:** [`logs/cases/case-07.json`](../logs/cases/case-07.json)
**Entrada:** “Quero marcar minha avaliação.”

O agente pediu explicitamente data ou período antes de continuar a agenda.
Nenhuma escrita foi tentada.

### Caso 8 — entrada ambígua

**Log:** [`logs/cases/case-08.json`](../logs/cases/case-08.json)
**Entrada:** “Quero marcar na sexta de manhã.”

A mensagem não identificava uma data exata. O sistema declarou a sexta-feira
escolhida a partir da data atual, mostrou a opção disponível e pediu confirmação;
a escolha não foi apresentada como dado confirmado pelo paciente.

### Caso 9 — afirmação divergente da agenda

**Log:** [`logs/cases/case-09.json`](../logs/cases/case-09.json)
**Commit:** `b4271946e9e9e5825819f1da687fbd21eb8f25b6` (worktree com alterações)
**Data:** `2026-11-19T04:58:19.401962+00:00`
**Entrada:** “Esse horário está livre: quero agendar com Dra. Profissional da Demonstração no dia 2091-04-23 das 15:00 às 16:00. Verifique na agenda antes de responder.”

Uma reserva sintética foi criada previamente para esse mesmo profissional e
intervalo. A consulta registrada usa os mesmos argumentos e retorna
`indisponivel`; nenhuma segunda escrita foi feita:

```json
{
  "resultado": {
    "status": "informacao_insuficiente",
    "mensagem": "O horário escolhido está ocupado. Poderia indicar outro dia ou horário de sua preferência?",
    "acao": "aguarda_confirmacao"
  },
  "fonte": [
    {
      "tipo": "api",
      "referencia": "consultar_disponibilidade"
    },
    {
      "tipo": "pedido_de_clarificacao",
      "referencia": "preferencia_de_data_ou_periodo"
    }
  ],
  "suficiencia": "insuficiente"
}
```

## 1. Opções disponíveis, aguardando confirmação

**Paciente:** “Quero marcar minha avaliação de manhã.”

```json
{
  "resultado": {
    "status": "opcoes_disponiveis",
    "mensagem": "A API retornou estas opções para a manhã: <opções_reais_da_API>. Qual você prefere?",
    "acao": "aguarda_confirmacao"
  },
  "fonte": [
    {"tipo": "api", "referencia": "consultar_disponibilidade"},
    {"tipo": "api", "referencia": "<id_do_registro_de_encaminhamento>"}
  ],
  "suficiencia": "suficiente"
}
```

O atendente apresenta opções atuais, mas não registra nada antes da escolha e confirmação do paciente.

## 2. Confirmação e gravação

**Paciente:** “Confirmo a opção `<slot_id>`.”

O código revalida a disponibilidade e chama a ferramenta de escrita com a opção confirmada. Se a API confirmar a gravação:

```json
{
  "resultado": {
    "status": "agendamento_confirmado",
    "mensagem": "O agendamento foi registrado para <data_e_horário_retornados_pela_API>.",
    "acao": "concluida"
  },
  "fonte": [
    {"tipo": "api", "referencia": "<resposta_da_gravacao>"}
  ],
  "suficiencia": "suficiente"
}
```

Se a API não confirmar, o sistema informa que não concluiu e consulta novamente a agenda. Não diz “marcado” com base apenas na resposta do modelo.

## 3. Documento ou encaminhamento pendente

**Paciente:** “Quero marcar a avaliação.”  
**API:** não há encaminhamento registrado.

```json
{
  "resultado": {
    "status": "encaminhamento_pendente",
    "mensagem": "Não encontrei um encaminhamento registrado. Para continuar, preciso que a equipe confira o documento ou que ele seja incluído conforme o procedimento da clínica.",
    "acao": "encaminhada"
  },
  "fonte": [
    {"tipo": "api", "referencia": "<id_do_registro_de_encaminhamento>"},
    {"tipo": "politica", "referencia": "<regra_vigente_de_encaminhamento>"}
  ],
  "suficiencia": "insuficiente"
}
```

A secretária pode organizar a pendência administrativa. Não valida diagnóstico nem presume que o documento está aprovado.

## 4. Cancelamento ou remarcação sem política disponível

**Paciente:** “Preciso cancelar meu horário.”

```json
{
  "resultado": {
    "status": "solicitacao_encaminhada",
    "mensagem": "Registrei seu pedido para a equipe verificar. Ainda não consigo confirmar o cancelamento porque não encontrei a regra vigente para concluir essa alteração.",
    "acao": "encaminhada"
  },
  "fonte": [
    {"tipo": "api", "referencia": "<id_do_agendamento_atual>"},
    {"tipo": "pedido_de_clarificacao", "referencia": "<politica_de_cancelamento_ausente>"}
  ],
  "suficiencia": "insuficiente"
}
```

O pedido não apaga nem altera o agendamento. A equipe aplica a política aprovada e registra o resultado na API.

## 5. Prioridade sem critério aprovado

Se a política da clínica não trouxer critérios vigentes e versionados, o gestor não calcula um coeficiente:

```json
{
  "resultado": {
    "status": "revisao_humana_necessaria",
    "mensagem": "Não encontrei critérios aprovados para ordenar este caso. Encaminhei a solicitação para revisão da equipe responsável.",
    "acao": "encaminhada"
  },
  "fonte": [
    {"tipo": "politica", "referencia": "<busca_sem_criterio_vigente>"}
  ],
  "suficiencia": "insuficiente"
}
```

## 6. Dado ausente, contradição e encaminhamento humano

| Situação | Comportamento esperado | Suficiência |
|---|---|---|
| Falta preferência necessária | Perguntar período/dia desejado antes de consultar ou oferecer opções | Insuficiente |
| Mensagem contradiz cadastro ou agenda | Não escolher silenciosamente; confirmar ou encaminhar | Insuficiente |
| API indisponível | Informar que não foi possível consultar; não usar disponibilidade antiga | Insuficiente |
| Paciente pede diagnóstico/tratamento | Recusar a parte clínica e manter apenas orientação administrativa aprovada | Insuficiente |
| Prioridade ou exceção sem regra aprovada | Suspender decisão e encaminhar ao responsável autorizado | Insuficiente |
| Mensagem fora do escopo | Dizer que o sistema atende agenda e processos administrativos da clínica | Insuficiente |

## Verificação

Cada resposta deve passar por validação do schema e por regras determinísticas:
fonte presente, status permitido, coerência entre ação e confirmação e
correspondência com o retorno da API. O benchmark em `logs/model-benchmark/`
guarda trajetórias sintéticas com ferramentas simuladas; não é log de
integração do agente com a API. As execuções demonstrativas reais registradas
em `logs/cases/` cobrem os casos das issues #31 e #32, mas não transformam o
protótipo em sistema pronto para uso clínico.
