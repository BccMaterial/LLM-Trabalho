# Memória e estado compartilhado

O estado mantém somente o necessário para retomar uma interação e coordenar as tarefas dos três agentes. Não substitui a API da clínica, o histórico clínico ou as políticas oficiais. A persistência ainda não está implementada.

## Identificadores

Cada conversa recebe `conversation_id` estável. O paciente é associado por identidade autenticada e `patient_id`; nome ou texto livre não serve como identificador. Um paciente pode ter várias conversas. O ID da conversa pode aparecer em logs, mas não dá acesso a dados sem autorização própria.

## Estado de curto prazo

Campos previstos:

- `conversation_id`, `patient_id` autorizado e etapa atual;
- intenções detectadas, dados explicitamente necessários e pendências;
- estado do encaminhamento (status e referência, não cópia do arquivo);
- prioridade/alerta e versão da regra aprovada, se houver;
- IDs das opções consultadas, escolha do paciente, confirmação exata e retorno da API;
- tarefas encaminhadas ao Gestor ou à Secretária, estado e responsável;
- fonte, suficiência, contagem de chamadas, tokens, tempo e erros da execução.

Cada agente recebe uma mensagem de tarefa estruturada com `task_id`, agente destino, objetivo, campos estritamente necessários, referências de fonte e schema de resposta. Ele devolve o mesmo `task_id`, status, resultado, fonte, suficiência e necessidade de revisão. O histórico livre não é transmitido integralmente entre agentes.

## Histórico e resumo

Mensagens podem ser mantidas pelo sistema de conversa segundo uma política institucional aprovada. Se o contexto precisar ser resumido, preservar somente a intenção, decisões já confirmadas, referências de fonte e pendências necessárias ao fluxo. O resumo não substitui a API e não deve registrar diagnóstico ou laudo em texto livre.

## Memória de longo prazo

Não há memória clínica de longo prazo do agente. Preferências estáveis só podem ser salvas quando necessárias, informadas pelo paciente e cobertas por política de consentimento e retenção. Suspeita, laudo, exame, encaminhamento e decisões clínicas permanecem nos sistemas oficiais, não na memória do modelo.

## Proteção e retenção

Arquivos locais de checkpoint, quando implementados, não devem ser versionados. O armazenamento precisa de controle de acesso, criptografia conforme infraestrutura e política de retenção definida pela clínica. Logs usam IDs técnicos e evitam mensagens completas, documentos e segredos. Prazo de retenção ainda não foi fornecido e não deve ser inventado.

## Limites atuais

O checkpoint e a comunicação estruturada entre agentes são propostas; não existem no código atual. A implantação precisa adicionar persistência protegida e mecanismo para reabrir tarefas pendentes sem duplicar agendamentos.
