# Prompts versionados

Os prompts de referência ficam em `prompts/` e são versionados junto com o código. Cada arquivo tem uma função limitada e deve produzir conteúdo compatível com o contrato de `docs/io.md`. Os prompts não substituem autorização, validação de schema, política clínica ou verificador determinístico.

| Arquivo | Agente | Técnica | Contrato | O que impede |
|---|---|---|---|---|
| `prompts/atendente_v1.txt` | Atendente | Roteamento por intenção e extração de campos necessários | Intenção, campos ausentes, mensagem e evidências em estrutura definida | Não inventar horários, não gravar sem confirmação, não responder diagnóstico |
| `prompts/gestor_v1.txt` | Gestor | Análise restrita aos critérios e registros autorizados | Prioridade/alerta estruturado com regra, fonte e suficiência | Não inferir gravidade clínica, não calcular com política ausente, não alterar agenda por conta própria |
| `prompts/secretaria_v1.txt` | Secretária | Checklist administrativo com base em política vigente | Itens presentes/ausentes, referência da política e encaminhamento | Não validar conteúdo clínico, não inventar documento exigido, não modificar prontuário |

## Parâmetros e avaliação

O modelo candidato não está escolhido. Em cada execução comparativa, registrar o modelo e versão exatos, provedor/endpoint, temperatura, limite de saída, modo de resposta estruturada, versão e hash do prompt, schemas, identificador do caso, chamadas de ferramenta, tokens, latência, resposta bruta e resultado do verificador. Alterar um desses itens entre candidatos invalida a comparação direta.

Preferir saída estruturada com schema validado e temperatura baixa quando o endpoint suportar essa configuração. O valor exato de cada parâmetro deve ser registrado no benchmark; não há configuração experimental executada neste repositório.

## Estado de integração

O prompt Atendente v1 é carregado por `src/agent/app.py`; o programa ainda envia uma mensagem fixa e não executa o laço nem as ferramentas do domínio. Os prompts do Gestor e da Secretária ainda não são chamados. A implementação futura deve registrar em cada execução qual prompt foi usado e acrescentar os fluxos, schemas e ferramentas descritos nos documentos.
