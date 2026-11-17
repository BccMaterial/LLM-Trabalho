# RAG como memória consultável

Neste projeto, a recuperação de conhecimento serve para apoiar decisões e
responder dúvidas administrativas da clínica. Ela não substitui a API da
clínica, que é a fonte dos dados individuais e mutáveis dos pacientes, nem
autoriza o agente a fazer diagnóstico.

> **Estado da implementação:** o repositório contém um primeiro serviço local
> de recuperação vetorial em `src/agent/policy_retrieval.py`, baseado em
> ChromaDB e no modelo de embeddings multilíngue descrito abaixo. Ainda não há
> documentos oficiais da clínica no índice, ingestão integrada nem validação
> com essas fontes. Os testes usam somente fixtures sintéticas identificadas
> como tal; elas não representam políticas da clínica.

## 1. Formas de recuperação escolhidas

| Forma usada | Com o quê | O que responde no case |
|---|---|---|
| Consulta estruturada | API/banco de dados da clínica, consultado por identificador do paciente e campos definidos | Dados cadastrais, encaminhamento registrado, agendamentos, disponibilidade e status/posição na fila |
| Busca vetorial | Implementação inicial do protótipo: ChromaDB e `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, com embeddings de 384 dimensões | Perguntas em linguagem natural sobre regras e orientações administrativas vigentes, como encaminhamentos, documentação e procedimentos aprovados de agendamento/cancelamento |

Assim, a resposta à pergunta “o RAG é vetorial ou é banco de dados?” é:
**a arquitetura combina os dois, para perguntas diferentes**. Registros individuais
exigem consulta estruturada; regras redigidas em linguagem natural podem ser
recuperadas semanticamente. A busca vetorial não deve ser usada para localizar
ou inferir dados pessoais de pacientes.

Não se propõe banco de grafo: as relações do escopo atual podem ser obtidas por
consultas estruturadas e pelos metadados dos documentos. Também não se propõe
busca textual como forma principal, pois as perguntas gerais previstas são
formuladas por assunto, não necessariamente repetindo os termos exatos das
políticas.

## 2. Corpus e manutenção

O corpus vetorial deve conter somente documentos institucionais necessários
para orientar o atendimento, por exemplo:

- política vigente de encaminhamentos;
- regras de agendamento e remarcação;
- procedimento de cancelamento e tratamento de vagas liberadas;
- checklist de documentos administrativos e responsável pela validação;
- regras sobre a quantidade e a sequência dos exames;
- orientações administrativas aprovadas para pacientes.

`docs/case.md` descreve somente regras iniciais do case e lacunas conhecidas;
não substitui políticas oficiais da clínica. Critérios de prioridade,
cancelamento/remarcação e checklist documental ainda precisam de aprovação da
coordenação. Sem uma versão oficial vigente, o agente deve informar
insuficiência e encaminhar a decisão. Não haverá simulação de exames nem
estimativa de prazo de diagnóstico. A equipe técnica deve publicar no índice
somente as versões aprovadas e vigentes.

**Frequência proposta:** revisar o corpus ao menos trimestralmente e atualizar
o índice sempre que uma política for criada, alterada ou revogada. Cada trecho
indexado guarda fonte, versão, identificadores do documento e seção, estado de
aprovação, responsável e data de aprovação quando aplicável, data de revogação
quando aplicável e datas de vigência. `PolicyRetriever.upsert` atualiza a
representação vetorial sem apagar versões anteriores; `search` filtra por estado
`approved` e vigência na data da consulta. Os estados aceitos são `pending`,
`approved`, `rejected` e `revoked`. Para excluir uma versão da recuperação, seu
estado deve ser atualizado para `revoked`. O diretório persistente pode ser
definido por `POLICY_INDEX_PATH`; por padrão, fica no cache local do usuário.
Dados de pacientes e de agenda mudam com maior frequência e devem ser
consultados na API, não indexados neste corpus.

O serviço recebe um trecho já delimitado por seção/artigo/tópico; ele não
implementa ingestão, divisão automática de documentos, autenticação de
aprovadores ou API de administração do índice. Essas operações precisam ser
integradas a uma origem institucional autorizada antes de uso real. A busca
normal exclui registros marcados como fixtures de teste.

## 3. Conjunto inicial de avaliação

As dez perguntas abaixo formam um primeiro dataset. Antes de usar com pacientes,
é necessário validar as respostas com documentos oficiais mantidos fora do
repositório e com registros de teste. Para as perguntas estruturadas, o item
indicado é o campo ou registro esperado na API; não há ainda um trecho
documental implementado para esses dados.

| # | Pergunta | Forma | Trecho, registro ou resultado esperado |
|---|---|---|---|
| 1 | Quantos exames um paciente pode realizar? | Vetorial | `docs/case.md`, “Regras de domínio — Quantidade de exames”: “Atualmente um paciente pode realizar entre 4 a 6 exames, dependendo do caso.” |
| 2 | De onde pode vir o encaminhamento médico? | Vetorial | `docs/case.md`, “Regras de domínio — Encaminhamentos”: o encaminhamento pode vir de um médico de outra clínica ou da própria clínica. |
| 3 | O que devo fazer se o horário que escolhi não estiver disponível? | Vetorial | `docs/case.md`, “Regras de domínio — Agendamentos”: o paciente deve ser informado e pode escolher outro horário. |
| 4 | Todo paciente faz exatamente seis exames? | Vetorial | `docs/case.md`, “Regras de domínio — Quantidade de exames”: a quantidade varia de 4 a 6, dependendo do caso; portanto, seis não é uma regra universal. |
| 5 | Quais exames estão marcados para mim? | Estruturada | Registro de agendamentos filtrado pelo identificador autenticado do paciente; retornar os exames e seus horários atuais. |
| 6 | Meu encaminhamento foi registrado? | Estruturada | Registro de encaminhamento associado ao paciente, incluindo seu estado de validação. |
| 7 | Quais horários estão disponíveis para meu agendamento? | Estruturada | Consulta de disponibilidade da agenda para os exames necessários; usar disponibilidade atual, não uma resposta armazenada no índice. |
| 8 | Qual é a minha posição ou situação na fila? | Estruturada | Registro atual de fila/status associado ao paciente. Se a API não fornecer posição, o sistema deve informar que não dispõe desse dado. |
| 9 | Quem aprovou a política de encaminhamentos vigente? | Estruturada | Metadado de aprovação da versão vigente da política, com responsável e data. Esse metadado precisa ser incluído quando a fonte oficial for cadastrada. |
| 10 | Qual prazo de diagnóstico a clínica garante? | Sem resposta no corpus | Não há prazo garantido documentado em `docs/case.md`. O agente deve dizer que não encontrou essa informação e não inventar um prazo. |

As perguntas 2 e 3 verificam a recuperação das regras de encaminhamento e
agendamento; a pergunta 4 verifica que uma faixa não seja reduzida a um valor
fixo. A pergunta 10 testa a recusa
quando a informação não consta do corpus. Para cada execução de avaliação,
registrar a resposta, a fonte recuperada, se a resposta foi sustentada pela
fonte e se houve recusa adequada.

## 4. Controle de versões

As políticas e suas versões são mantidas fora do repositório. No índice, cada
trecho deve conter metadados de fonte, versão, estado (vigente ou revogado) e
datas de vigência. A recuperação normal deve considerar somente versões
vigentes; as versões revogadas ficam disponíveis apenas para auditoria, sem
serem usadas para responder dúvidas de pacientes.

**Avaliação proposta:** quando as fontes oficiais e o índice estiverem
disponíveis, verificar que as consultas retornam a versão vigente e citam sua
fonte. Registrar como falha se uma versão revogada for usada na resposta. Os
testes atuais verificam os filtros de status e vigência com documentos
sintéticos marcados como fixtures; eles não validam a relevância semântica do
modelo nem políticas reais.

## 5. Corte e `k` da busca vetorial

Estas decisões aplicam-se somente à busca vetorial implementada; não se aplicam às
consultas estruturadas da API.

- **Estratégia de corte:** dividir por seção, artigo ou tópico da política,
  preservando título, condições e consequência no mesmo trecho. As regras do
  case são curtas e organizadas por assunto; um corte por tamanho fixo poderia
  separar, por exemplo, a regra de encaminhamento da informação de que ele pode
  ser emitido por médico da própria clínica ou de outra clínica.
- **Sobreposição:** não usar sobreposição fixa como regra inicial. Preferir
  limites estruturais e repetir no metadado/título o contexto necessário. Se
  documentos reais tiverem artigos longos, reavaliar com exemplos de consulta.
- **`k = 3` inicial:** recuperar até três trechos para compor o contexto. É um
  valor inicial para testar cobertura de perguntas que dependem de mais de uma
  regra sem carregar muitos trechos irrelevantes. Avaliar respostas com
  `k = 1`, `3` e `5` no dataset; manter o menor valor que preserve as respostas
  corretas e as exceções.

Os valores de corte e `k` são hipóteses de protótipo, não resultados medidos.
Devem ser revistos após a inclusão dos documentos oficiais e a execução do
conjunto de avaliação.
