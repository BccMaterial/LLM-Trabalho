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

> **Estado da implementação:** o fluxo de agendamento usa `StateGraph`,
> `interrupt`, `MemorySaver` e `Command(resume=...)`. O paciente confirma,
> rejeita ou edita uma proposta; após a aprovação, o código revalida o horário
> antes da escrita. A proposta expira em 120 segundos; o grafo também tem
> limites de execução e classificação de términos/erros. A aprovação de
> documentos para RAG e as operações do Gestor ainda não estão implementadas.

## 1. Ações que exigem intervenção

| Ação | Quem decide | O que deve ser apresentado | Resultado da aprovação |
|---|---|---|---|
| Criar um agendamento | Paciente autenticado | Profissional e horário propostos; a identidade do paciente vem da sessão autenticada | O grafo revalida a disponibilidade e só então executa a ferramenta de criação |
| Aprovar um documento para o RAG | Responsável autorizado pela clínica | Documento, origem, versão, datas de vigência, finalidade e efeito de disponibilizá-lo aos agentes | A versão aprovada pode ser publicada/indexada; somente ela pode ser recuperada para respostas |
| Criar, remover ou atualizar um recurso | Gestor ou responsável autorizado conforme a política da clínica | Tipo e identificador do recurso, valores atuais e propostos e consequência da mudança | O controlador valida a autorização e aplica somente a mudança aprovada |

Os tipos de recurso que o Gestor poderá alterar, os perfis autorizados para
cada tipo e a semântica de remoção ainda precisam ser definidos com a clínica.
Até isso ser definido, o agente não deve executar alterações de recursos.

## 2. Confirmação de agendamento

O agente recebe uma proposta de agendamento do LLM. O nó
`request_approval` valida que o profissional está ativo e interrompe o grafo
com o profissional e os horários apresentados. A identidade do paciente vem
da autenticação, não dos argumentos enviados pelo modelo. Antes de criar o
registro, o nó `revalidate_availability` consulta a disponibilidade novamente.

Respostas aceitas:

- **aprovar:** autoriza exatamente a proposta interrompida;
- **rejeitar:** encerra essa tentativa sem criar o agendamento;
- **editar:** valida os campos obrigatórios, atualiza a proposta e solicita
  nova aprovação.

Resposta inválida não aprova a ação; a tentativa termina e a proposta pendente
pode ser retomada em outra invocação. A aprovação expira após 120 segundos,
verificados quando a interrupção é retomada. Depois da aprovação, se a
disponibilidade mudou ou a API falhou, o código não grava o horário antigo e
encerra a tentativa com uma resposta.

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

No fluxo implementado, `request_approval` chama `interrupt` antes da escrita.
O CLI associa o checkpointer `MemorySaver` ao `thread_id` da conversa e retoma
com `Command(resume=...)`. `validate_professional` é um nó separado antes da
pausa; uma retomada normal continua em `request_approval` e não repete essa
consulta. Uma edição invalida essa validação e faz o fluxo validá-la novamente.
A escrita só ocorre depois da aprovação e da revalidação da disponibilidade.

Como o checkpointer é em memória, uma aprovação pendente não é durável após
reinício do processo. Não há timer em segundo plano: uma aprovação vencida é
rejeitada quando alguém tenta retomar o grafo, sem executar a escrita. Silêncio
nunca aprova a ação.

## 6. Repetição e idempotência

O fluxo gera `approved_action_key` a partir do identificador da conversa, da
ferramenta e dos argumentos canônicos aprovados, normalizando a identidade do
paciente para a identidade autenticada. O dicionário `completed_actions`
impede repetir a escrita no mesmo estado/checkpoint e retorna que a ação já
havia sido executada, guardando apenas o identificador e os horários do
agendamento. Essa proteção depende do `MemorySaver`: não persiste após
reinício e não cobre a janela entre uma escrita externa bem-sucedida e a
atualização do checkpoint. Idempotência persistente na API ainda está pendente.
Publicação no RAG e alterações de recursos pelo Gestor não estão implementadas.

## 7. Evidências para a entrega

Os testes do agente cobrem aprovação, rejeição, edição, revalidação e repetição
da ação aprovada. O CLI não mantém um log de auditoria dessas decisões. Não
registrar senhas, documentos completos ou conteúdo clínico desnecessário.

Perfis adicionais e tipos de recurso ainda não definidos permanecem decisões
pendentes; não preencher esses campos com regras inventadas.
