# Memória do agente

Este documento descreve a proposta de memória para o agente de agendamentos. A persistência de conversas ainda não está implementada no código do projeto.

## Identificação da conversa

Cada conversa deve receber um `conversation_id` único e estável, preferencialmente um UUID, criado no início do atendimento. Esse identificador permite recuperar o contexto da conversa mesmo que o processo do agente seja reiniciado. Se o paciente estiver autenticado, o identificador pode ser associado ao seu cadastro; nome ou texto da mensagem não devem ser usados como identificador.

O `conversation_id` identifica a conversa, enquanto o identificador do paciente identifica a pessoa. Uma pessoa pode ter mais de uma conversa.

## Memória de curto prazo e checkpoint

A memória de curto prazo é o contexto necessário para continuar o atendimento: mensagens recentes, dados já informados para o agendamento, etapa atual do fluxo e um resumo do que ocorreu anteriormente.

O checkpoint deve guardar esse estado para que a conversa possa ser retomada. Na execução local, a proposta é gravar um arquivo por conversa em:

```text
data/checkpoints/<conversation_id>.json
```

O arquivo é atualizado ao longo da conversa e não deve ser versionado no Git, pois pode conter dados pessoais. Em produção, o armazenamento deve ser persistente e protegido, com acesso controlado e políticas de retenção adequadas; o diretório local é apenas a convenção inicial para desenvolvimento.

## Quando a janela de contexto enche

O limite da janela é tratado antes de enviar uma chamada que excederia o contexto disponível. O agente deve:

1. preservar no checkpoint os dados necessários para continuar o fluxo e o estado atual;
2. resumir as partes antigas da conversa que ainda sejam relevantes;
3. manter as mensagens recentes necessárias para interpretar a solicitação atual;
4. montar o próximo contexto com as instruções, o resumo, as mensagens recentes e apenas as memórias de longo prazo pertinentes.

Assim, o histórico completo pode permanecer no armazenamento da conversa sem ser reenviado integralmente ao modelo em cada chamada. O resumo não deve substituir os dados oficiais do paciente nem inventar informações ausentes.

## Memória de longo prazo

A memória de longo prazo pode conter informações estáveis que ajudem em atendimentos futuros, como preferências de comunicação ou de horário informadas pelo paciente. Ela deve ser recuperada no início de uma nova conversa e somente quando for relevante para a solicitação.

Não se deve copiar automaticamente toda a conversa para essa memória. Sintomas, suspeitas, laudos, resultados de exames e outros dados clínicos pertencem ao histórico cadastral/clínico do paciente, com as proteções próprias desse sistema; não devem ser tratados como preferências nem registrados na memória do agente por padrão. Informações temporárias, detalhes de uma conversa e dados sem utilidade para atendimentos futuros também ficam fora da memória de longo prazo.

Qualquer gravação de memória duradoura deve ser limitada ao necessário, transparente para o paciente e sujeita às regras de privacidade, consentimento e retenção definidas para o projeto.

## Resumo dos ciclos

| Tipo de memória | Conteúdo | Persistência e uso |
|---|---|---|
| Curto prazo | Mensagens, resumo e estado do atendimento | Checkpoint identificado por `conversation_id`; atualizado durante a conversa e recuperado ao retomá-la |
| Longo prazo | Preferências estáveis e úteis para atendimentos futuros | Associada ao paciente, consultada no início de conversas e atualizada somente com informações apropriadas |
