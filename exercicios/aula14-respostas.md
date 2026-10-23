#### ASI01 — Sequestro de objetivo do agente

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |simulação e conversa |
| Cenário de ataque |prompt injection |
| Impacto |alto |
| Mitigação | Uso de guard-rails nos prompts |

#### ASI02 — Uso indevido e exploração de ferramenta

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |simulação |
| Cenário de ataque |alteração da data |
| Impacto |medio |
| Mitigação |garantia da autenticidade |

#### ASI03 — Abuso de identidade e privilégio

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |conversa |
| Cenário de ataque |descobrir informações privadas |
| Impacto |medio |
| Mitigação |autenticidade do usuario |

#### ASI04 — Cadeia de suprimentos agêntica

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |dependencias |
| Cenário de ataque |explorar vunerabilidade |
| Impacto |baixo |
| Mitigação |garantir a confiança |

#### ASI05 — Execução inesperada de código

| Campo | Resposta |
|---|---|
| Existe no case? |não |
| Onde | |
| Cenário de ataque | |
| Impacto | |
| Mitigação | |

#### ASI06 — Envenenamento de memória e de contexto

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |simulação e conversa |
| Cenário de ataque |alteração da memoria com objetivo de obter algo |
| Impacto |medio |
| Mitigação |garantia que o contexto não possa ser alterado |

#### ASI07 — Comunicação insegura entre agentes

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |entre os agentes |
| Cenário de ataque |alteração no transporte |
| Impacto |alto |
| Mitigação |garantir um canal seguro de comunicação |

#### ASI08 — Falhas em cascata

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |conversa |
| Cenário de ataque |queda da api |
| Impacto |alto |
| Mitigação |armazenar a informação mesmo se a api tiver caido |

#### ASI09 — Exploração da confiança humano-agente

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |conversa |
| Cenário de ataque |informação incorreta |
| Impacto |leve |
| Mitigação |validar as informações passadas |

#### ASI10 — Agentes desgovernados

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |consulta |
| Cenário de ataque |consultar politica errado |
| Impacto |baixo |
| Mitigação |garantia das consultas corretas |


### risco aceito:
#### ASI04 — Cadeia de suprimentos agêntica

| Campo | Resposta |
|---|---|
| Existe no case? |sim |
| Onde |dependencias |
| Cenário de ataque |explorar vunerabilidade |
| Impacto |baixo |
| Mitigação |garantir a confiança |


aceito dada a baixa chance de acontecer,limita o fato de ter um orgão, se alguma falha for encontrada tal evento mudaria o jeito de lidar com a falha


