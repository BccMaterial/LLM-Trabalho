# Prompts versionados

Os prompts de referência ficam em `src/prompts/` e são versionados junto com o código como recursos do pacote. Cada arquivo tem uma função limitada e deve produzir conteúdo compatível com o contrato de `docs/io.md`. Os prompts não substituem autorização, validação de schema, política clínica ou verificador determinístico.

| Arquivo | Agente | Técnica | Contrato | O que impede |
|---|---|---|---|---|
| `src/prompts/atendente_v1.txt` | Atendente | Roteamento por intenção e extração de campos necessários | Intenção, campos ausentes, mensagem e evidências em estrutura definida | Não inventar horários, não gravar sem confirmação, não responder diagnóstico |
| `src/prompts/gestor_v1.txt` | Gestor | Análise restrita aos critérios e registros autorizados | Prioridade/alerta estruturado com regra, fonte e suficiência | Não inferir gravidade clínica, não calcular com política ausente, não alterar agenda por conta própria |
| `src/prompts/secretaria_v1.txt` | Secretária | Checklist administrativo com base em política vigente | Itens presentes/ausentes, referência da política e encaminhamento | Não validar conteúdo clínico, não inventar documento exigido, não modificar prontuário |

## Parâmetros e avaliação

Nenhum candidato foi aprovado para uso com pacientes; Gemini 3.5 Flash-Lite é apenas o candidato provisório da próxima iteração, conforme [`docs/modelos.md`](modelos.md). A rodada registrou modelo e endpoint exatos, temperatura, limite de saída, hash do prompt/schema/casos, chamadas de ferramenta, tokens, latência, resposta e validação no relatório em `logs/model-benchmark/`. Alterar esses itens entre candidatos invalida a comparação direta.

Preferir saída estruturada com schema validado e temperatura baixa quando o endpoint suportar essa configuração. Na rodada registrada, a temperatura foi zero e o schema foi solicitado no prompt e validado localmente; não foi usada garantia nativa de saída JSON.

## Estado de integração

O prompt Atendente v1 é carregado por `src/agent/app.py`; o agente inicia com uma mensagem demonstrativa, mantém turnos e chama ferramentas pela API Flask do projeto. Gestor e Secretária ainda não são chamados. Os registros de benchmark exercitam ferramentas simuladas, não substituem teste de integração do agente contra a API. O verificador e a barreira determinística para escrita continuam pendentes.
