# RAG como memória consultável

Neste projeto, a recuperação de conhecimento serve para apoiar decisões e
responder dúvidas administrativas da clínica. Ela não substitui a API da
clínica, que é a fonte dos dados individuais e mutáveis dos pacientes, nem
autoriza o agente a fazer diagnóstico.

> **Estado da implementação:** o repositório contém um primeiro serviço local
> de recuperação vetorial em `src/agent/policy_retrieval.py`, baseado em
> ChromaDB e no modelo de embeddings multilíngue descrito abaixo. Ainda não há
> documentos oficiais da clínica no índice nem validação com essas fontes. O
> agente expõe a ferramenta `consultar_politica`, que consulta o serviço quando
> o modelo precisa responder sobre regras administrativas. Os testes usam
> somente fixtures sintéticas identificadas como tal; elas não representam
> políticas da clínica.

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

### Integração ao agente

A recuperação é exposta como ferramenta `consultar_politica`, em vez de uma
etapa fixa para toda mensagem. Assim, perguntas de agenda e dados individuais
continuam usando a API estruturada, e o modelo só consulta o corpus para dúvidas
de política. O índice exclui fixtures de teste e o serviço filtra documentos
que não estejam aprovados e vigentes. A resposta precisa citar exatamente uma
fonte retornada pela ferramenta; o contrato rejeita referências de política
inventadas. Sem trechos recuperados, o prompt orienta o agente a declarar a
insuficiência e não completar a resposta com conhecimento geral.

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
documental implementado para esses dados. A avaliação executável do RAG cobre
as perguntas vetoriais 1 a 4 e 10. As perguntas estruturadas 5 a 9 aparecem no
relatório como não executadas: precisam de fixtures e/ou endpoints da API que
não fazem parte deste conjunto de avaliação.

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

As perguntas 2 e 3 verificam regras condicionais de encaminhamento e
agendamento; a pergunta 4 verifica que uma faixa não seja reduzida a um valor
fixo. A pergunta 10 testa a insuficiência quando a informação não consta do
corpus. O relatório registra chamadas, candidatos, fontes aceitas, suficiência
e resultado da recuperação. A resposta final do LLM não foi avaliada.

O executor reproduzível é:

```powershell
poetry run python -m scripts.evaluate_rag --output docs/rag_evaluation.json
```

Ele usa ChromaDB efêmero, o modelo de
embeddings configurado e somente fixtures sintéticas derivadas do case. O JSON
registra pergunta, chamada, `k`, candidatos com distâncias, fontes aceitas,
suficiência e resultado. Não chama o LLM nem a API; portanto, mede recuperação
e roteamento esperado, não a qualidade da resposta final do modelo. As
perguntas 5 a 9 são registradas como `not_executed_missing_api_fixture`, sem
fabricar resultados de paciente.

A resposta final e a recusa determinística sem fonte são cobertas por testes do
grafo; não foram avaliadas com chamadas a um LLM real.

## 4. Controle de versões

As políticas e suas versões são mantidas fora do repositório. No índice, cada
trecho deve conter metadados de fonte, versão, estado (vigente ou revogado) e
datas de vigência. A recuperação normal deve considerar somente versões
vigentes; as versões revogadas ficam disponíveis apenas para auditoria, sem
serem usadas para responder dúvidas de pacientes.

Na avaliação sintética, uma política revogada com um prazo de diagnóstico
fictício foi inserida no índice, mas não apareceu entre as fontes retornadas em
nenhuma das duas estratégias de corte. A pergunta sobre prazo terminou com
suficiência `insuficiente` e nenhuma fonte aceita. Os candidatos vetoriais
irrelevantes são registrados no JSON, mas não são expostos ao agente como
evidência. Isso confirma o filtro de status para esta fixture; não valida
políticas reais.

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
  regra sem carregar muitos trechos irrelevantes.

### Medições no corpus sintético

Foram comparados trechos por seção (**estrutural**) com janelas fixas de 96
caracteres sem sobreposição (**fixo**). A suficiência exige cobertura lexical
mínima de 0,5 dos termos significativos da pergunta em trechos do mesmo
documento, após normalização de acentos e plurais. Esse corte conservador
rejeitou os candidatos irrelevantes da pergunta 10; é uma heurística inicial,
não uma validação semântica geral.

| Corte | `k` | Perguntas respondíveis (1–4) | Exceções (2–4) | Falso positivo na 10 |
|---|---:|---:|---:|---:|
| Estrutural | 1 | 3/4 | 2/3 | 0 |
| Estrutural | 3 | 4/4 | 3/3 | 0 |
| Estrutural | 5 | 4/4 | 3/3 | 0 |
| Fixo, 96 caracteres | 1 | 3/4 | 2/3 | 0 |
| Fixo, 96 caracteres | 3 | 4/4 | 3/3 | 0 |
| Fixo, 96 caracteres | 5 | 4/4 | 3/3 | 0 |

Com `k = 3`, ambos os cortes recuperaram as quatro fontes esperadas e trataram
as três perguntas condicionais/excepcionais; `k = 5` não aumentou a cobertura.
Mantemos corte estrutural e `k = 3` como configuração inicial: preserva cada
regra e sua exceção no mesmo trecho, enquanto o corte fixo pode separar essas
partes e exigir múltiplos trechos. A medição cobre apenas quatro perguntas
respondíveis e uma sem resposta, todas sintéticas. Repetir com fontes oficiais,
mais paráfrases e avaliação da resposta final antes de qualquer uso real.
