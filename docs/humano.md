# Intervenção humana

Este documento define os pontos em que uma pessoa precisa autorizar ou revisar
uma ação do sistema. A pessoa que responde depende do tipo de ação:

1. o paciente ou responsável confirma o próprio agendamento;
2. um responsável autorizado aprova a entrada de um documento no RAG;
3. um gestor autorizado confirma mudanças em recursos da clínica.

Uma mensagem comum do usuário faz parte da conversa. Ela só conta como
aprovação quando responde a uma solicitação explícita que identifica a ação e
seus argumentos. O modelo não pode interpretar silêncio, ambiguidade ou uma
resposta referente a outra opção como aprovação.

> **Estado da implementação:** os três pontos abaixo são requisitos do fluxo.
> O agente atual executa um laço de conversa e chama ferramentas, mas ainda
> não implementa pausas com `interrupt`, checkpoint e retomada do LangGraph. A
> descrição de uma ferramenta no prompt não substitui uma barreira de aprovação
> validada pelo código.

## 1. Ações que exigem intervenção

| Ação | Quem decide | O que deve ser apresentado | Resultado da aprovação |
|---|---|---|---|
| Criar um agendamento | Paciente ou responsável autenticado | Paciente, profissional, data, horário e demais campos que serão gravados | O controlador revalida a disponibilidade e solicita à API a criação do agendamento exato |
| Aprovar um documento para o RAG | Responsável autorizado pela clínica | Documento, origem, versão, datas de vigência, finalidade e efeito de disponibilizá-lo aos agentes | A versão aprovada pode ser publicada/indexada; somente ela pode ser recuperada para respostas |
| Criar, remover ou atualizar um recurso | Gestor ou responsável autorizado conforme a política da clínica | Tipo e identificador do recurso, valores atuais e propostos e consequência da mudança | O controlador valida a autorização e aplica somente a mudança aprovada |

Os tipos de recurso que o Gestor poderá alterar, os perfis autorizados para
cada tipo e a semântica de remoção ainda precisam ser definidos com a clínica.
Até isso ser definido, o agente não deve executar alterações de recursos.

## 2. Confirmação de agendamento

O agente pode consultar a agenda e apresentar opções retornadas pela API. Antes
de criar o registro, deve pedir que o paciente ou responsável confirme uma
opção específica. O pedido deve mostrar todos os campos que serão usados na
gravação, incluindo paciente, profissional, data e horário. Não basta perguntar
“confirma?” sem identificar a opção.

Respostas aceitas:

- **aprovar:** autoriza exatamente a opção apresentada;
- **rejeitar:** encerra essa tentativa sem criar o agendamento;
- **editar:** volta à conversa para corrigir ou escolher outra opção; a opção
  alterada precisa ser apresentada e confirmada novamente.

Depois da aprovação, o código deve consultar novamente a disponibilidade. Se
ela mudou, não deve gravar o horário antigo: deve explicar a situação e
apresentar novas opções. Sem resposta, com resposta ambígua ou fora do prazo,
o agendamento permanece pendente e nenhuma gravação é feita.

## 3. Aprovação de documentos para o RAG

Um documento só pode ser disponibilizado para recuperação depois de um
responsável autorizado da clínica aprovar sua versão. A aprovação deve estar
associada à versão exata do documento, não apenas ao seu título. Registrar, no
mínimo:

- identificador e origem do documento;
- versão ou hash do conteúdo;
- finalidade e agentes que podem consultá-lo;
- estado (`pendente`, `aprovado`, `rejeitado` ou `revogado`);
- responsável e data da decisão;
- datas de vigência, quando existirem na fonte oficial.

O documento pendente ou rejeitado fica fora do índice consultável. Uma edição
gera uma nova versão e requer nova aprovação. Se uma política for revogada, o
sistema deve removê-la da recuperação normal, preservando o histórico exigido
para auditoria. A busca vetorial contém políticas administrativas aprovadas;
dados atuais e individuais de pacientes continuam sendo consultados na API.

## 4. Criação, remoção e atualização de recursos pelo Gestor

Antes de cada operação, o sistema deve mostrar à pessoa autorizada:

- a ação solicitada (`criar`, `remover` ou `atualizar`);
- o tipo e identificador do recurso;
- os valores atuais e os valores propostos;
- a consequência operacional da mudança.

Uma aprovação vale apenas para essa combinação de ação, recurso e argumentos.
Se qualquer argumento mudar, o sistema deve pedir nova aprovação. Rejeição
encerra a tentativa sem alteração. Edição substitui os argumentos propostos e
exige que a pessoa aprove a versão editada.

A política de remoção ainda precisa definir se o recurso será desativado ou
excluído, quem pode aprovar cada tipo de remoção e como manter o histórico. Até
essa regra existir, o agente deve encaminhar o pedido para a equipe e não
alterar o recurso.

## 5. Pausa, retomada e ausência de resposta

No grafo LangGraph, cada ação sujeita a aprovação deve parar antes de qualquer
efeito externo. A pausa apresenta a proposta exata à pessoa. A retomada recebe
uma das respostas aceitas — aprovar, rejeitar ou editar — e o código valida a
resposta e a autorização antes de continuar.

A pausa deve usar `interrupt` e um checkpointer associado a um identificador de
conversa (`thread_id`). A retomada deve usar `Command(resume=...)`. Como o nó
que contém o `interrupt` executa novamente desde o início na retomada, nenhuma
escrita na API ou publicação no índice pode ocorrer antes da pausa.

O prazo de resposta e o destino do encaminhamento depois do vencimento ainda
precisam ser definidos. O comportamento seguro enquanto isso não for decidido
é manter a ação pendente, não aprová-la automaticamente e não executar a
alteração. Se o checkpointer escolhido for em memória, a perda de uma aprovação
pendente após reinício do processo deve ser documentada como limitação.

## 6. Repetição e idempotência

Uma retomada repetida, uma mensagem duplicada ou uma repetição da chamada não
pode criar duas reservas, publicar duas vezes a mesma versão ou duplicar uma
mudança de recurso. Cada ação aprovada deve receber uma chave de idempotência
derivada do conteúdo aprovado, da ação e do identificador do recurso. Se a
mesma ação já tiver sido aplicada, retornar um resultado equivalente a
`ja_existia` e não repetir o efeito externo.

## 7. Evidências para a entrega

Os logs devem mostrar a proposta apresentada, o perfil que respondeu, a
decisão (`aprovar`, `rejeitar` ou `editar`), a retomada e o resultado da
validação. Não registrar senhas, documentos completos ou conteúdo clínico
desnecessário.

Incluir pelo menos uma execução em que uma pessoa edita a proposta antes de
aprovar e uma repetição da mesma aprovação. A evidência deve demonstrar que a
alteração editada foi a aplicada e que a repetição não duplicou o efeito.

Os prazos, perfis e tipos de recurso ainda não definidos devem permanecer
identificados como decisões pendentes; não preencher esses campos com regras
inventadas.
