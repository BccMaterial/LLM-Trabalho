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

## Issue #25 — ablação do guardrail de privacidade da agenda

### Desenho experimental

O alvo da ablação é o bloco `Guardrail de privacidade da agenda` em
`src/prompts/atendente_v1.txt`. A hipótese é que removê-lo aumente a
probabilidade de o agente repetir ou resumir campos internos de agendamentos,
enquanto o prompt atual deve recusar o pedido e oferecer somente ajuda com
disponibilidade ou agendamento.

O caso `privacidade_agenda` em `benchmarks/casos.json` fornece apenas dados
sintéticos e marca como proibidos o paciente, profissional, descrição clínica,
status e identificador do registro. A métrica `forbidden_output_detected`,
gravada no JSON/CSV do benchmark, detecta a presença desses campos na resposta.
Também são comparados schema, fontes, suficiência, chamadas de ferramenta,
tentativas de escrita e revisão humana de segurança.

Para manter a comparação válida, controle e ablação devem usar o mesmo modelo,
schema, casos, ferramentas simuladas, temperatura, limites e número de
repetições. A variante sem o bloco deve ser um arquivo temporário passado por
`--prompt`; o prompt versionado permanece protegido até a decisão final.

### Execução reproduzível

```bash
poetry run python -m src.agent.benchmark --dry-run
poetry run python -m src.agent.benchmark --output-dir logs/model-benchmark/issue-25-controle
poetry run python -m src.agent.benchmark --prompt /caminho/atendente_v1_sem_privacidade.txt \
  --output-dir logs/model-benchmark/issue-25-ablacao
```

As execuções devem ser feitas somente com dados sintéticos e os relatórios
devem registrar os hashes do prompt, schema e casos. No ambiente desta
implementação, o `--dry-run` foi validado, mas não há chaves
`GROQ_API_KEY`/`GEMINI_API_KEY` configuradas para produzir os dois relatórios
com chamadas aos provedores. Portanto, a decisão empírica da Issue #25 ainda
depende dessa execução; o guardrail atual permanece no prompt por segurança.
