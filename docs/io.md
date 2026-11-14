# Contrato de entrada e saída

Os exemplos deste documento definem o formato esperado; não são registros de execução. Valores entre `<...>` são campos que devem vir da mensagem, da API ou de política oficial. Nenhum horário, regra clínica ou resultado é inventado pelo modelo.

## Entrada

O atendimento recebe uma mensagem em português e metadados separados do texto, como `conversation_id` e identidade autenticada. O sistema interpreta a intenção, identifica lacunas e consulta apenas fontes autorizadas. Metadados não são tratados como conteúdo escrito pelo paciente.

## Saída obrigatória

```json
{
  "resultado": {
    "status": "<status_controlado>",
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

O schema deve ser validado em código. `fonte` aponta para a ferramenta/registro ou política consultada. Quando a informação for insuficiente, `resultado` informa o dado ou a aprovação que falta.

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
    {"tipo": "api", "referencia": "<consulta_de_disponibilidade>"},
    {"tipo": "api", "referencia": "<status_do_encaminhamento>"}
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
    {"tipo": "api", "referencia": "<consulta_de_encaminhamento>"},
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
    {"tipo": "api", "referencia": "<agendamento_atual>"},
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

Cada resposta deve passar por validação do schema e por regras determinísticas: fonte presente, status permitido, coerência entre ação e confirmação, e correspondência com o retorno da API. Esses exemplos ainda não são logs de execução; evidências reais devem ser registradas em `logs/` quando o agente e as ferramentas forem implementados.
