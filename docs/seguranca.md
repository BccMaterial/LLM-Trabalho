# Segurança e proteção de dados

## Escopo e premissas

Este documento descreve o código executável do protótipo, não o desenho-alvo
de `docs/arquitetura.md`. Os testes e benchmarks usam dados sintéticos. Não há
política fornecida pela clínica sobre bases legais, prazos de retenção,
fornecedores aprovados ou resposta a incidentes; essas decisões são marcadas
como **LACUNA**, não presumidas. Não usar dados reais de pacientes neste
protótipo.

## Canais de entrada não confiáveis

- **Texto livre no CLI:** `run_scheduling_flow` recebe a mensagem e a adiciona
  ao estado antes da chamada ao modelo ([CLI](../src/agent/cli.py#L24),
  [workflow](../src/agent/workflows/scheduling.py#L201)). Não há garantia de
  que instruções no texto sejam confiáveis.
- **Argumentos e resultados de ferramentas:** chamadas do modelo passam por
  `execute_tool`; nomes e campos precisam ser validados no código, não apenas
  pela descrição/esquema enviado ao provedor ([dispatcher](../src/agent/tools.py#L107)).
- **Requisições HTTP à API:** parâmetros de consulta e corpos JSON são entradas
  externas. Autenticação, autorização por role e validação de payload são
  aplicadas pelos controllers; nenhuma identidade informada pelo modelo
  substitui a sessão autenticada ([agendamentos](../src/api/controllers/appointment_controller.py#L26)).
- **Corpus RAG e configuração local:** chunks são dados externos ao prompt,
  mesmo quando marcados como aprovados; `LLM_BASE_URL`, `API_BASE_URL` e as
  configurações do juiz também podem ser mal configuradas. A busca filtra
  status/vigência, mas não transforma o conteúdo recuperado em instrução
  confiável ([recuperação](../src/agent/policy_retrieval.py#L231),
  [configuração TLS](../src/network_security.py#L5)).

## Riscos em ordem de impacto

| Prioridade | Cenário concreto e capacidade existente | Impacto | Localização e mitigação |
|---|---|---|---|
| 1 — alto | Uma credencial técnica `agent` comprometida podia listar cadastros de pacientes e dados completos de profissionais, além de listar, alterar ou cancelar agendamentos — incluindo `suspeita_paciente`. | Exposição de dados pessoais/de saúde e alteração/cancelamento indevido de agenda ou cadastro profissional. | O agente não lista usuários nem lê/escreve dados completos de profissionais; recebe apenas IDs e nomes de profissionais ativos. A API nega ao agente listagem integral, edição, cancelamento e criação de agendamentos. Disponibilidade retorna somente `disponivel`/`indisponivel`; a ferramenta rejeita `patient_id`. A criação usa o cookie da sessão autenticada do paciente, e a API exige que o `patient_id` corresponda à identidade da sessão. Implementação: políticas de [agendamentos](../src/api/policies/appointment_authorization_policy.py#L1), [usuários](../src/api/policies/user_authorization_policy.py#L4) e [profissionais](../src/api/policies/professional_authorization_policy.py#L1); [consulta de disponibilidade](../src/api/controllers/appointment_controller.py#L57), [criação](../src/api/controllers/appointment_controller.py#L26), [lista de profissionais minimizada](../src/api/controllers/professional_controller.py#L82) e [cliente da API](../src/agent/integrations/api.py#L98). |
| 2 — alto | `LLM_BASE_URL`, `JUDGE_LLM_BASE_URL` e `API_BASE_URL` são configurações externas. Conversa/resultados vão ao LLM; a API recebe credenciais, cookies de sessão e, nas rotinas de demonstração, o token administrativo. HTTP remoto permitiria interceptar ou alterar esses dados em trânsito. | Exposição ou manipulação de dados de saúde, identidade e credenciais. | Os clientes do agente, rotinas de demonstração e juiz rejeitam HTTP remoto e exigem HTTPS; HTTP só é aceito para loopback local. Implementação: [validador comum](../src/network_security.py#L5), [cliente LLM](../src/agent/integrations/llm.py#L14), [cliente API](../src/agent/integrations/api.py#L23), [dados de demonstração](../src/agent/demo_data.py#L18) e [fixtures do juiz](../src/judge/fixtures.py#L54). HTTPS protege o transporte, mas não define retenção, uso ou localização dos dados pelo provedor. |
| 3 — moderado | Um arquivo como `.env.production` ou `.env.local` podia ser adicionado por engano: antes, somente `.env` estava ignorado. | Chaves e senhas poderiam ser publicadas e permanecer no histórico Git mesmo após remoção do arquivo. | `.env.*` agora é ignorado, com exceção explícita de `.env.example`. É uma barreira contra inclusão acidental, não impede `git add -f`, cópia de segredo para outro arquivo nem substitui revisão/varredura de segredos. Regra: [`.gitignore`](../.gitignore#L10). |
| 4 — moderado | Um trecho recuperado por RAG pode conter instruções maliciosas ou conflitantes. A busca retorna conteúdo aprovado/vigente ao modelo, mas aprovação e cobertura lexical não neutralizam prompt injection. | Resposta administrativa incorreta e tentativa de acionar ferramentas fora da intenção do usuário; os controles de autorização, aprovação e validação continuam sendo a fronteira para efeitos colaterais. | O índice atual contém apenas fixtures/documentos de demonstração e a busca filtra status e vigência. Esse filtro não é uma defesa contra instruções embutidas; não indexar corpus real até existir revisão editorial e controles adicionais. Código: [busca RAG](../src/agent/policy_retrieval.py#L231) e [dispatch da ferramenta](../src/agent/tools.py#L107). |

## Controles implementados

| Controle | O que bloqueia | O que deixa de fazer | Falha | Custo/efeito operacional | Evidência automatizada |
|---|---|---|---|---|---|
| Menor privilégio, identidade e resposta minimizada | Leitura de cadastro de pacientes, dados completos de profissionais, listagem de agendamentos, suspeitas, edição, cancelamento ou criação com a credencial técnica; filtro de disponibilidade por paciente; criação para outra identidade. | O agente só recebe nomes/IDs de profissionais ativos e disponibilidade sem dados do paciente; não tem operações de escrita. Paciente cria apenas para si; gerência/administração trata correções/cancelamentos. O cadastro ainda revalida conflitos antes da escrita. | Fail-closed: rotas técnicas não permitidas retornam 403; argumentos extras são rejeitados; sessão paciente com identidade divergente recebe 403. | Acrescenta endpoints minimizados e requer sessão paciente válida para criar; correções/cancelamentos exigem fluxo administrativo. | `test_appointments_agent_access.py`, `test_users_agent_access.py`, `test_professionals_agent_access.py` verificam bloqueios/minimização; `test_appointments_patient_access.py` verifica identidade; `test_tools.py` verifica rejeição de `patient_id` e uso do cookie de paciente. |
| HTTPS para conexões configuráveis | `API_BASE_URL`, endpoints LLM/juiz remotos em HTTP, URLs sem host ou com credenciais embutidas. | Não permite conexões remotas somente HTTP. | Fail-closed, exceto HTTP em `localhost`/IP de loopback para desenvolvimento local. | Endpoints de desenvolvimento remotos precisam oferecer HTTPS; endpoints locais permanecem utilizáveis. | `test_tools.py`, `test_demo_data.py`, `test_fixtures.py` e `test_configuration.py` tentam HTTP remoto e comprovam rejeição; `test_tools.py` também verifica HTTP em loopback. |
| Ignorar arquivos `.env.*` | Inclusão acidental de variantes de arquivos de ambiente no Git. | Não impede cópia de segredos para outros arquivos, inclusão forçada ou exposição já existente. | O Git ignora por padrão; não é uma validação de runtime e pode ser contornado deliberadamente. | Nenhum efeito no runtime; `.env.example` continua versionável. | `test_env_gitignore.py` verifica a regra com `git check-ignore`. |

### Verificação do histórico de ambiente

A issue não especifica comandos adicionais do enunciado. Foram verificadas as
referências ao arquivo em todas as refs locais disponíveis, sem imprimir valores
de ambiente:

```text
git log --all --full-history --oneline -- .env
(sem saída: nenhum commit/ref local contém o caminho .env)

git log --all --full-history --format= --name-only -- '*.env' '.env.*'
.env.example

git log --all -S "OPENAI_API_KEY=" --oneline
(correspondências de nomes de variáveis e placeholders; nenhuma chave real identificada)

git ls-files --error-unmatch .env
tracked_env_file=no

```

Não foi encontrada chave real no histórico local pesquisado; as correspondências
de `OPENAI_API_KEY=` são nomes de variáveis e placeholders. O arquivo `.env` não
está versionado. Isso não prova que segredos nunca tenham sido copiados para
outro caminho, refs remotas não obtidas, arquivos locais ignorados ou serviços
externos. `.env.example` contém placeholders e valores de desenvolvimento; não
deve ser reutilizado como configuração de produção. Se uma chave for encontrada
em outra revisão ou serviço, revogue-a no provedor e substitua-a antes de
retomar o uso.

## Fluxo e inventário de dados

| Local/fluxo | Dados que podem estar presentes e finalidade | Base legal | Retenção atual ou pendência |
|---|---|---|---|
| Entrada do paciente | Texto livre pode conter identificadores e dados de saúde; é usado para responder e, quando solicitado, propor agendamento. | **LACUNA:** controlador da clínica deve definir e documentar a base aplicável antes de qualquer dado real, incluindo a análise dos arts. 7 e 11 da LGPD. O protótipo não presume consentimento nem outra hipótese legal. | Não há retenção independente configurada na entrada; o conteúdo permanece no estado/checkpoint enquanto o processo está ativo. |
| API e banco | Cadastro tem nome, username, CPF e e-mail. Agendamento guarda paciente, profissional, horário e `suspeita_paciente`, que pode revelar dado de saúde. Finalidade: autenticação e operação da agenda. | **LACUNA:** mesma definição pelo controlador; finalidade técnica não estabelece, por si só, base legal. | Não há prazo de retenção/exclusão definido pelo projeto (**LACUNA**). A retenção física segue a configuração externa do banco, sem política de expurgo implementada aqui. |
| Estado/checkpoint do agente | Mensagens, argumentos de ferramentas, proposta pendente e resultados necessários para retomar o fluxo. Pode conter conteúdo livre e dados retornados pela API. | **LACUNA** para dados reais; uso somente sintético no protótipo. | `MemorySaver` mantém o checkpoint na memória do processo, sem prazo por conversa ou exclusão seletiva; termina ao encerrar o processo. Não é armazenamento durável. |
| Índice RAG | Trechos e metadados de documentos de política; a recuperação não escreve mensagens ou dados de pacientes. O corpus disponível é de demonstração/fixtures, não política oficial da clínica. | **LACUNA** para documentos reais: definir autorização, finalidade e base antes de indexá-los. | Chroma persiste localmente no diretório configurado (`POLICY_INDEX_PATH` ou cache do usuário); não há expiração automática (**LACUNA**). |
| Traces e avaliações | Por padrão, traces guardam atributos minimizados; `--capture-synthetic-payloads` opt-in inclui mensagens, respostas, argumentos/resultados de ferramentas e eventos de aprovação, e a suíte rejeita casos que não sejam de desenvolvimento/sintéticos. O benchmark e a suíte também podem gravar respostas/contextos em `logs/model-benchmark` e `evals/judge_runs`. | **LACUNA** se entradas reais forem introduzidas; não habilitar captura nem usar dados reais nesses artefatos. | Jaeger local é volátil; arquivos locais não têm prazo de retenção/expurgo definido (**LACUNA**). Não registrar ou versionar traces com dados reais. |
| Provedor LLM | A aplicação envia mensagens da conversa e resultados de ferramenta ao endpoint configurado para gerar resposta. | **LACUNA:** clínica deve aprovar provedor, finalidade, contrato e base legal antes de dados reais. | Retenção, treinamento, região, suboperadores e exclusão dependem do provedor/configuração; não são verificáveis pelo código (**LACUNA**). TLS não resolve essas questões. |

## Risco aceito e limites

Aceitamos, **somente no protótipo com dados sintéticos**, que o checkpoint
mantenha mensagens e resultados na memória até o processo ser encerrado. Isso
permite retomar uma pausa de aprovação sem criar uma cópia durável de conversa.
O custo é não haver expiração nem remoção seletiva enquanto o processo roda; um
processo longo mantém o conteúdo mais tempo que um turno.

Também aceitamos que texto recuperado do RAG possa influenciar o modelo, pois o
índice atual contém somente conteúdo de demonstração. O filtro de aprovação e
vigência não impede instruções maliciosas dentro de um documento. A inclusão de
políticas oficiais ou de qualquer fonte editável por terceiros dispara
reavaliação antes de ativar esse corpus.

Esse risco deixa de ser aceitável antes de qualquer piloto com dados reais,
persistência de checkpoints ou execução do agente como serviço de longa duração.
Qualquer uma dessas mudanças dispara reavaliação de controle de acesso,
expiração, exclusão, observabilidade e política de retenção, com aprovação do
controlador da clínica. O protótipo não deve ser apresentado como pronto para
produção clínica.
