# Model card — Atendente e apoio operacional

> **Retrato do sistema em 23/11/2026.** Este documento descreve o protótipo
> executável e suas evidências; não é aprovação clínica nem descrição do desenho
> futuro de Gestor/Secretária. A issue #58 depende das evidências das issues
> #59–#61, que ainda estão em PRs separados.

## 1. Identificação

- **Sistema:** Atendente para apoio administrativo a avaliações
  neuropsicológicas.
- **Versão do pacote:** `0.1.0` (`pyproject.toml`). Rodadas instrumentadas também
  registram o rótulo de avaliação, o commit e a versão do sistema.
- **Estado:** protótipo local; não implantado em clínica e não aprovado para
  uso com pacientes.
- **Arquitetura existente:** um agente Atendente, uma API de demonstração e um
  fluxo LangGraph. Os agentes Gestor/Secretária, fila clínica e verificador
  completo são desenho futuro, não capacidades atuais
  ([arquitetura implementada e alvo](./arquitetura.md)).

## 2. Finalidade e usuários previstos

O protótipo demonstra atendimento administrativo por mensagens e apoio a
consultas/agendamentos em dados sintéticos. O paciente ou responsável pode
informar preferências e, se autenticado, confirmar o próprio agendamento. A
equipe técnica usa o CLI, as avaliações e os traces para desenvolvimento.

Não há integração com uma clínica real nem autorização institucional para
operar com dados reais. O uso previsto nesta etapa é desenvolvimento e avaliação
com fixtures sintéticas. A finalidade futura de apoiar uma clínica não amplia
por si só a autoridade do agente.

## 3. Autoridade e fronteiras de uso

O modelo interpreta mensagens e propõe chamadas. O código valida o contrato,
autenticação, disponibilidade e aprovação antes de qualquer escrita. O agente
não tem autoridade clínica.

**No fluxo implementado:**

- Pode consultar profissionais ativos e a agenda/disponibilidade pela API
  configurada; a fonte autoritativa para dados mutáveis é a API, não o RAG.
- Pode propor um agendamento. Uma escrita só pode ocorrer após autenticação do
  paciente, confirmação explícita da proposta exata, revalidação do horário e
  autorização da API.
- `approve`, `reject` e `edit` são decisões distintas; edição exige nova
  validação e aprovação. Aprovação vencida ou inválida não autoriza escrita.
- Não pode diagnosticar, recomendar tratamento, decidir prioridade clínica,
  cancelar/remarcar, consultar dados de outro paciente ou transformar texto
  recuperado em política oficial.

**Controles de segurança associados à #59:** a PR #71 separa a conta técnica
`agent` da sessão do paciente, limita leitura de agenda/profissionais e nega
operações administrativas ao agente; a criação exige a sessão do próprio
paciente. A mesma PR exige HTTPS para endpoints remotos e mantém HTTP apenas em
loopback local. Esses controles e testes estão na
[PR #71](https://github.com/BccMaterial/LLM-Trabalho/pull/71); essa PR ainda é
uma dependência separada desta branch.
Os controles server-side detalhados nela não fazem parte do commit-base desta
branch e não devem ser considerados implantados até que a PR seja integrada e
validada.

**Credenciais:** `LLM_API_KEY`, `API_AGENT_USER`/`API_AGENT_PASSWORD` (ou o
fallback temporário `API_USER`/`API_PASSWORD`) e, na avaliação, as credenciais
do juiz são configuração local. Os valores não pertencem a este documento,
ao trace nem ao repositório. O arquivo `.env` não existe neste ambiente; por
isso não é possível identificar o modelo/endpoints ativos de uma instalação.

**Limites por execução:** até 8 etapas do workflow, 10 chamadas externas, 12.000
tokens reportados, 120 s por turno, 1.000 tokens de saída por chamada, 30 s
por chamada externa, 1 repetição idêntica de ferramenta e 120 s para retomar
uma aprovação; `recursion_limit=32` é uma barreira adicional do LangGraph
([constantes](../src/agent/workflows/execution.py#L4)). São limites de
engenharia, não garantias de latência ou segurança clínica.

**Evidências:** [pedido/aprovação e expiração](../src/agent/actions.py#L108),
[revalidação](../src/agent/workflows/scheduling.py#L752) e testes de
[aprovação](../tests/unit/agent/test_app.py#L349),
[revalidação](../tests/unit/agent/test_app.py#L586) e
[expiração](../tests/unit/agent/test_app.py#L745). Os controles de menor
privilégio e transporte estão registrados na [PR #71](https://github.com/BccMaterial/LLM-Trabalho/pull/71),
incluindo as políticas `src/api/policies/*_authorization_policy.py` e testes
`tests/integration/api/appointment/access/`.

## 4. Ferramentas e integrações

| Integração | Uso existente | Fronteira/estado |
|---|---|---|
| LLM compatível com API OpenAI | Interpreta mensagens e propõe chamadas | Endpoint, chave e modelo vêm de variáveis locais; não são fixados pelo código |
| API de usuários/profissionais/agendamentos | Autenticação, consulta e operação demonstrativa de agenda | API local; não é a API de uma clínica nem uma grade real de horários livres |
| `consultar_profissionais` | Lista profissionais ativos | Não deve revelar IDs ao paciente |
| `consultar_disponibilidade` | Consulta registros/intervalos existentes | Não calcula uma grade clínica completa |
| `confirmar_agendamento` | Solicita a operação após aprovação e revalidação | Não cancela nem remarca; a API aplica autenticação e autorização |
| `consultar_politica` | Busca trechos administrativos no RAG local | O índice não contém políticas oficiais aprovadas; não usar para dados de paciente/agenda |
| Jaeger local | Recebe traces OTLP para desenvolvimento | Armazenamento em memória, sem autenticação e apenas para dados sintéticos |

O Gestor, a Secretária, a fila, a decisão de prioridade e a aprovação/publicação
de políticas oficiais não estão implementados ([estado do grafo](./arquitetura.md)).

## 5. Modelo e provedor

O modelo efetivamente chamado é selecionado por `LLM_MODEL`; `LLM_BASE_URL` e
`LLM_API_KEY` configuram endpoint e credencial. A comparação exploratória
registrada em [modelos](./modelos.md) selecionou Gemini 3.5 Flash-Lite para
continuar o protótipo: nos sete casos daquela rodada, 7/7 schemas/tool calls
passaram, mas a suficiência foi correta em somente 4/7. Essa decisão não fixa
o modelo ativo, não aprova seu uso com pacientes e não demonstra benefício
clínico.

A configuração da conta importa: a documentação do benchmark registra
tratamento de dados diferente entre modalidades gratuitas e pagas. Até que
privacidade, retenção, região, contrato e finalidade do provedor sejam
aprovados pelo controlador da clínica, só usar dados sintéticos. O juiz LLM é
uma integração separada e também usa credenciais/modelo configurados localmente.

## 6. Dados

- **Avaliação disponível:** casos sintéticos versionados e dados fictícios da
  API de demonstração. Não foram usados dados reais nesta avaliação.
- **Dados que uma implantação futura poderia receber:** mensagens livres,
  identidade, encaminhamento e informações de agenda; podem conter dados
  pessoais e de saúde. A base legal, finalidade, controlador, operador e
  autorização institucional são **LACUNA**.
- **Fluxo:** texto e contexto necessário podem ser enviados ao provedor LLM;
  fatos mutáveis da agenda vêm da API. O RAG é um corpus separado e não deve
  guardar conversas.
- **Estado:** `MemorySaver` mantém o checkpoint apenas na memória do processo;
  não há memória de longo prazo. Encerrar o processo perde a retomada
  ([memória](./memoria.md)).
- **Minimização:** os spans não incluem mensagens, argumentos ou respostas
  completas, identificadores de pacientes/agendamentos, credenciais ou texto
  de exceção ([atributos de trace](./observabilidade.md)).

## 7. Avaliação, decisão e reconstrução de execução

**Evidência de qualidade do Atendente:** a comparação da suíte sintética em
[evals-comparison.md](./evals-comparison.md) relata 15/18 casos conclusivos
(83%) antes e 17/20 (85%) depois do prompt v2. O prompt mudou entre as rodadas,
logo não é uma comparação causal isolada. A amostra tem apenas 20 casos e não
mede correção clínica, experiência do paciente ou benefício para a clínica.
Separadamente, o juiz obteve 18/20 acordos (90%) na validação
([metodologia e limitações](./evals.md)); esse número mede concordância do juiz,
não qualidade do agente.

A #61 pré-define um SLI de aprovação com alvo de 90%, janela de coorte e mínimo
de 30 execuções válidas. A ferramenta de correlação/métricas já está no
[analisador](../src/judge/observability_metrics.py), mas não há 30 execuções
instrumentadas válidas nem relatório observado. O alvo de 90% é uma meta, não
um resultado; valor medido, p50/p95, custo e consumo do orçamento de erro são
**LACUNA**.

### Reconstrução exigida somente com trace

**LACUNA:** não há trace selecionável nesta entrega. Jaeger não está ativo
(`127.0.0.1:16686` não respondeu) e não existe `.env` para executar o agente.
Além disso, a instrumentação atual é deliberadamente minimizada: registra
versão/commit, nomes e status de ferramentas, decisão de aprovação, categorias
da saída e motivo de término, mas não registra texto da entrada/saída, argumentos
nem resultados completos. Portanto não é possível reconstruir, somente do
trace, a entrada e todo o contexto/fontes de uma decisão. Logs de avaliação não
são substitutos para esta exigência.

Quando houver um trace sintético real, a reconstrução deve citar o `trace_id` e
verificar no próprio Jaeger: `run_id`/`case_id`, versões/commit, spans `chat` e
`execute_tool`, decisão/proposta de aprovação, categorias da saída e motivo de
término. Para incluir entrada/contexto exatos sem enfraquecer a minimização,
é necessário decidir se um perfil de evidência restrito a casos sintéticos pode
referenciar o caso versionado por `case_id`; não adicionar texto de paciente a
traces de produção.

## 8. Limites conhecidos

- Um único Atendente; não há os três agentes do desenho-alvo, fila clínica,
  cálculo de horários livres nem políticas oficiais no RAG.
- Os testes e benchmarks são sintéticos; não demonstram validade clínica,
  segurança geral ou benefício.
- A dependência externa do LLM pode falhar, limitar ou mudar preço/política;
  a saída continua sujeita a validação de código e fonte.
- A idempotência da escrita depende do checkpoint em memória e não cobre toda
  falha entre a escrita externa e a persistência do checkpoint.
- O exportador pode perder traces quando Jaeger/coletor está indisponível; o
  atendimento pode continuar sem a evidência. Não há retenção durável ou alerta
  operacional configurado.
- Não há política institucional de retenção, resposta a incidentes, suspensão
  de produção nem avaliação clínica independente.

## 9. Riscos aceitos e falha de controles

**Aceitos somente no protótipo sintético:** volatilidade do checkpoint em
memória e influência potencial de conteúdo recuperado no RAG, cujo corpus atual
é de demonstração. Isso não constitui aceitação de risco para dados reais.

**Controles e falhas observáveis:**

- Aprovação ausente, inválida ou expirada, revalidação indisponível e erro de
  autorização devem impedir a escrita; evidências incluem os testes do campo 3
  e os testes de acesso da [PR #71](https://github.com/BccMaterial/LLM-Trabalho/pull/71).
- O cliente de serviços remotos deve falhar fechado se a URL não satisfizer
  HTTPS; HTTP é reservado a loopback na #59. Essa proteção ainda depende da
  integração da [PR #71](https://github.com/BccMaterial/LLM-Trabalho/pull/71).
- Uma falha do exportador Jaeger não interrompe o atendimento e pode perder
  traces; não há alerta que garanta detecção. Até definir observabilidade e
  resposta operacional, não usar o sistema com dados reais.
- **LACUNA:** não há análise de risco aprovada pela clínica, responsável formal
  pela aceitação, teste de resposta a incidentes ou procedimento de suspensão.

**Evidências:** [testes do fluxo de aprovação](../tests/unit/agent/test_app.py#L349)
e [documentação de observabilidade, falhas e retenção](./observabilidade.md);
os testes de autorização/TLS pertencem à [PR #71](https://github.com/BccMaterial/LLM-Trabalho/pull/71).

## 10. Supervisão humana e suspensão

O paciente autenticado decide sobre o próprio agendamento; a proposta exata é
apresentada antes da escrita. Revisão/aprovação de política RAG e mudanças de
recursos pela clínica pertencem ao desenho futuro e não estão implementadas.
Nenhum silêncio ou resposta ambígua vale como aprovação
([intervenção humana](./humano.md)).

**LACUNA — perfil autorizado a suspender:** não há papel institucional
designado, contato de plantão, botão de bloqueio ou procedimento de reativação.
O operador local consegue encerrar o processo, mas isso não define autoridade
organizacional. A clínica e a equipe técnica devem designar, respectivamente,
um responsável clínico e um operador autorizado, definir gatilhos de suspensão,
canal de incidente, evidência a preservar e aprovação para reativar.

## 11. Registro, acesso e retenção

- Traces Jaeger: destino local em `127.0.0.1:16686`/OTLP `4317`, armazenamento
  em memória, sem autenticação; reiniciar Jaeger apaga os traces. Usar somente
  dados sintéticos ([Compose](../infra/compose.yaml),
  [observabilidade](./observabilidade.md)).
- Avaliações versionadas guardam `run.json`, `results.json` e `summary.json`.
  `results.json` pode conter respostas e resultados de ferramentas; manter local,
  sintético e fora de commits quando não estiverem aprovados para publicação.
- O relatório do analisador da #61 guarda métricas e IDs de traces com metadados
  minimizados; não foi gerado para 30 execuções reais.
- **LACUNA:** política de acesso, prazo de retenção, descarte, backup e
  preservação para auditoria não foram definidos pela instituição. Antes de
  qualquer uso real, definir responsável, perfis, prazos, descarte verificável
  e backend protegido; não reutilizar o Jaeger local sem autenticação.

**Evidências:** [exportação e atributos minimizados](./observabilidade.md),
[geração das rodadas](../src/judge/run_suite.py#L84) e armazenamento volátil
configurado em [`infra/compose.yaml`](../infra/compose.yaml).

## 12. Histórico de mudanças desde a Parte 2

| Data | Issue/commit | Mudança relevante para este card |
|---|---|---|
| 20/11/2026 | #55 — `a039b55` | Dataset sintético versionado para avaliação |
| 20/11/2026 | #56 — `548d415` | Níveis de avaliação, rubrica e validação do juiz |
| 20–21/11/2026 | #57 — `e755617`, `4553f6d` | Suíte de execução, realinhamento do dataset e comparação 15/18 → 17/20 |
| 23/11/2026 | #59 — `dfa8140`, [PR #71](https://github.com/BccMaterial/LLM-Trabalho/pull/71) | Menor privilégio, autorização e HTTPS; PR separada |
| 23/11/2026 | #60 — `f77f042`, [PR #72](https://github.com/BccMaterial/LLM-Trabalho/pull/72) | Spans GenAI minimizados e exportação OTLP |
| 23/11/2026 | #61 — `e9043be`, [PR #74](https://github.com/BccMaterial/LLM-Trabalho/pull/74) | Correlação e ferramenta de métricas/SLO; medições reais pendentes |
| 23/11/2026 | #62 — `3ceef6e`, [PR #73](https://github.com/BccMaterial/LLM-Trabalho/pull/73) | Documentação reprodutível da Entrega 3 |

Os commits de #59, #60, #61 e #62 estão em branches/PRs separadas; o histórico
não significa que todos os controles ou evidências já foram integrados à
`main`. Este card está empilhado sobre a branch de #61.

## Lacunas e correções propostas

1. **Trace real e reconstrução:** iniciar Jaeger, rodar um caso sintético após
   configurar o ambiente e guardar o `trace_id`; decidir se `case_id` ligado ao
   dataset sintético fornece detalhe suficiente, sem exportar conteúdo clínico.
2. **SLI/SLO observado:** após commit e checkout limpo, executar pelo menos duas
   rodadas completas (40 tentativas), coletar os traces e comitar o relatório
   JSON/Markdown. Publicar valor do SLI e orçamento de erro somente se houver
   pelo menos 30 execuções válidas.
3. **Autoridade e suspensão:** clínica designa formalmente quem pode aprovar
   políticas/exceções e quem pode suspender/reativar o serviço; adicionar um
   procedimento testável e auditável.
4. **Dados e provedor:** controlador define base legal, provedor permitido,
   finalidade, acesso, retenção e resposta a incidentes antes de dados reais.
5. **Risco operacional:** definir alerta para falha de exportação, backend
   protegido, retenção/descarte verificáveis e avaliação independente antes de
   qualquer piloto.
