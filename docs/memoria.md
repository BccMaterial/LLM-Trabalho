# Memória, checkpoint e ciclo de vida

## Decisão para este protótipo

O agente mantém apenas o estado necessário durante a conversa corrente. **Não há memória de longo prazo**: uma conversa não ensina fatos, preferências ou procedimentos para conversas futuras. Essa escolha evita criar uma cópia paralela de dados pessoais ou clínicos sem uma política institucional de consentimento, acesso e retenção. O protótipo usa somente dados fictícios e não depende de acesso à clínica.

O fluxo implementa um checkpoint de curto prazo com o `MemorySaver` do LangGraph. Ele é volátil e fica na memória do processo. Não é banco, arquivo persistente nem memória de longo prazo. O serviço de recuperação vetorial do RAG é uma estrutura separada e não recebe gravações das conversas.

## Fronteiras: estado, memória e RAG

| Estrutura | Escopo e finalidade neste projeto | Conteúdo e fonte | Persistência |
|---|---|---|---|
| **Checkpoint (curto prazo)** | Retomar nós e pausas da mesma conversa, inclusive uma aprovação pendente, sem repetir efeitos colaterais | Estado do workflow: mensagens, identificador da conversa, ação pendente, resultado da aprovação, resultados de ferramentas, contadores e controle de ações concluídas | `MemorySaver`, somente na memória do processo; desaparece quando o processo termina |
| **Memória de longo prazo** | Lembrar fatos ou episódios de uma conversa para outra | **Não usada.** Nenhum conteúdo da conversa é promovido a memória | Nenhum armazenamento |
| **RAG (conhecimento consultável)** | Recuperar conteúdo de referência para responder perguntas, sem aprender com as conversas | Corpus separado, curado e versionado; o protótipo atual usa documentos/fixtures sintéticos e não políticas oficiais da clínica | Índice vetorial local, conforme `docs/rag.md`; a recuperação não grava o diálogo |

Serializar o checkpoint integral em uma memória de longo prazo não acrescentaria uma capacidade útil ao case: duplicaria mensagens e resultados de ferramenta, inclusive informação que pode ser pessoal, enquanto os fatos mutáveis do paciente devem ser consultados na API. O RAG responde outra pergunta: localiza trechos de um corpus de referência; não retoma a execução nem guarda o que o paciente disse.

## Tipos de memória de longo prazo

As três categorias foram avaliadas e ficam **fora do escopo da implementação** desta etapa:

| Tipo | Decisão | Justificativa para o case |
|---|---|---|
| **Episódica** — eventos de conversas passadas | Não implementar | Reaproveitar relatos, erros ou decisões de outras pessoas poderia expor dados e enviesar o atendimento. O protótipo não precisa aprender com casos anteriores. |
| **Semântica** — fatos sobre pessoas ou entidades | Não implementar | Cadastro, encaminhamento e agenda são mutáveis e têm como fonte de autoridade a API, não a memória do modelo. Preferências não serão armazenadas sem necessidade e política de consentimento/retenção aprovada. |
| **Procedural** — regras de como executar tarefas | Não implementar como memória adaptativa | Regras do fluxo ficam no código e nos prompts versionados; políticas administrativas, quando existirem, devem vir de fonte aprovada via RAG. O agente não aprende procedimentos a partir de conversas. |

Consequência: **volume de escrita de memória de longo prazo por execução é zero registros e zero bytes**. Não existe escritor de memória, identificador de registro, chave de idempotência de memória ou retorno `ja_existia`. O checkpoint é mantido pelo mecanismo do LangGraph; a idempotência das ações de agendamento é uma proteção distinta e não transforma essas ações em memória.

## Identificação da conversa e conteúdo do checkpoint

O CLI cria um `conversation_id` aleatório no início da sessão e o envia como `thread_id` ao LangGraph. Mensagens posteriores daquele processo reutilizam a mesma conversa. Uma nova execução do CLI cria outro identificador, mesmo para a mesma pessoa; duas conversas simultâneas também têm threads distintos. O identificador não é identidade nem autorização. A identidade autenticada, quando existe, vem da sessão da API.

Para retomar a execução, o checkpoint precisa preservar o estado operacional, incluindo histórico de mensagens, ferramenta/argumentos pendentes, pausa de aprovação, decisão recebida, retornos de ferramenta e chaves de ações já concluídas. Como mensagens e retornos podem conter conteúdo fornecido pelo usuário ou dados retornados pela API, o checkpoint deve ser tratado como dado potencialmente sensível, mesmo que o protótipo de demonstração use dados fictícios. Ele não deve ser copiado para logs ou persistência durável sem uma política aprovada.

O `MemorySaver` permite retomada enquanto o mesmo processo está ativo. Encerrar o CLI ou reiniciar o processo descarta os checkpoints e impossibilita retomar uma conversa interrompida entre processos. O protótipo não oferece exclusão seletiva nem prazo de expiração por conversa; essa limitação deve ser resolvida antes de qualquer implantação com dados reais.

## Conversa longa e limite de contexto

O estado preserva a ordem das mensagens para que uma confirmação ou resultado recente não seja perdido. **Hoje não há sumarização nem descarte automático de mensagens antigas.** Os limites de passos, chamadas, tokens de saída e tempo restringem uma execução, mas não implementam uma política de compactação do histórico acumulado entre turnos.

Política do protótipo: não truncar silenciosamente o começo ou o fim do histórico. Se o provedor não aceitar o contexto enviado, encerrar o turno com erro/insuficiência, sem declarar sucesso nem executar uma ação pendente. O paciente precisará iniciar uma conversa nova e fornecer novamente os dados administrativos necessários; o sistema deve consultar a API e o RAG outra vez. Nenhum diagnóstico, laudo ou histórico clínico deve ser resumido para contornar o limite.

Uma política de resumo seletivo só deve ser implementada se o sistema passar a precisar de conversas maiores. Nesse caso, precisará de testes que demonstrem quais dados são preservados e quais são removidos; ela não é apresentada aqui como capacidade existente.

## Correção, decaimento e remoção

| Causa de esquecimento | Decisão e comportamento |
|---|---|
| **Contradição/correção** | Não há fato persistido entre conversas para sobrescrever. Dentro de uma conversa, o agente deve tratar a fonte atual da API como autoridade e consultar novamente dados mutáveis; não deve resolver divergência criando uma lembrança. O comportamento de resolução depende do fluxo e ainda precisa ser verificado caso a caso. |
| **Decaimento** | Não aplicável à memória de longo prazo, pois ela não existe. O corpus RAG tem ciclo próprio de revisão/revogação descrito em `docs/rag.md`; não é memória do paciente. |
| **Remoção solicitada** | Não há registro de memória de longo prazo a remover. O checkpoint é descartado ao fim do processo, mas não existe remoção seletiva de thread durante a execução. Não usar dados reais enquanto essa limitação persistir. |

Não configuramos prazo clínico ou legal de retenção porque o grupo não recebeu uma política da clínica. Para demonstrações, use somente dados sintéticos e encerre o processo ao terminar. Se uma futura implantação exigir checkpoint durável ou memória de longo prazo, a equipe deverá definir acesso, retenção, exclusão e idempotência antes de ativá-los.

## Estado da implementação

Implementado hoje: checkpoint em memória de processo no workflow LangGraph; identificador de thread por conversa; índice RAG separado do estado do workflow. Não implementado: persistência entre processos, remoção seletiva, sumarização/compactação de contexto e qualquer memória episódica, semântica ou procedural.

Uma conversa nova deve começar sem mensagens, aprovações ou resultados de ferramentas da conversa anterior. Qualquer futura implementação de memória entre conversas exige uma política própria de necessidade, consentimento, retenção, exclusão e idempotência antes de ser ativada.
