# Mudanças e lacunas desde a Parte 2

Este registro relaciona lacunas observáveis na entrega anterior às correções
concretas da Entrega 3. As correções descrevem o que existe no repositório; não
representam validação clínica nem autorização para uso com dados reais.

| Lacuna identificada | Correção e estado atual | Evidência e commits |
| --- | --- | --- |
| O benchmark da Parte 2 comparava modelos com casos e ferramentas simuladas; não avaliava o comportamento do agente integrado. Também faltava um conjunto versionado de casos do sistema. | Foi criado um golden dataset com 20 casos e uma suíte que executa o ponto de entrada real `src.agent.cli.run_scheduling_case`, registra cada rodada e compara resultados por classe. | [Limites do benchmark anterior](modelos.md); [dataset](../evals/golden_dataset.json); [suíte](../src/judge/run_suite.py); [comparação registrada](evals-comparison.md). Commits: [a039b55](https://github.com/BccMaterial/LLM-Trabalho/commit/a039b55), [e755617](https://github.com/BccMaterial/LLM-Trabalho/commit/e755617), [4553f6d](https://github.com/BccMaterial/LLM-Trabalho/commit/4553f6d), [a36e39b](https://github.com/BccMaterial/LLM-Trabalho/commit/a36e39b). |
| Não havia uma justificativa auditável para escolher o nível de avaliação nem evidência de validação do juiz LLM. | As propriedades foram mapeadas para verificações determinísticas, de trajetória, de resultado ou juiz; 20 saídas foram rotuladas, os desacordos classificados e a decisão de adoção registrada. | [Metodologia e limitações](evals.md); [validação versionada](../evals/judge_validation.json). Commits: [548d415](https://github.com/BccMaterial/LLM-Trabalho/commit/548d415), [74ce28c](https://github.com/BccMaterial/LLM-Trabalho/commit/74ce28c). |
| A confirmação de horários tinha comportamento ambíguo em entradas que não especificavam uma opção exata. | As regras de confirmação do prompt foram explicitadas e comparadas. A comparação registrada melhorou de 83% para 85% na média geral e eliminou os casos ambíguos daquela amostra, mas também registrou regressões em outras classes; não demonstra segurança clínica nem que todos os casos estejam resolvidos. | [Prompt do Atendente](../src/prompts/atendente_v1.txt); [resultados e regressões](evals-comparison.md). Commit da mudança: [222f480](https://github.com/BccMaterial/LLM-Trabalho/commit/222f480); evidência das rodadas: [a36e39b](https://github.com/BccMaterial/LLM-Trabalho/commit/a36e39b). |
| Uma execução não tinha traces GenAI consultáveis para relacionar versão, modelo, ferramentas, aprovações e término. | Foram adicionados spans OpenTelemetry para invocação do agente, chamadas ao modelo e ferramentas, com atributos minimizados, exportação OTLP/gRPC para Jaeger local e instruções de consulta. O destino local não é um backend de produção e não possui política institucional de retenção. | [Plano e limites de observabilidade](observabilidade.md); [configuração local](../infra/compose.yaml). Commit: [f77f042](https://github.com/BccMaterial/LLM-Trabalho/commit/f77f042). |

## Limites das evidências e do estado atual

As duas rodadas usadas na comparação estão em
[`evals/runs/20261121T020151Z-eaaccc1c`](../evals/runs/20261121T020151Z-eaaccc1c)
e
[`evals/runs/20261121T020604Z-760891ad`](../evals/runs/20261121T020604Z-760891ad).
Ambos os `run.json` registram o mesmo commit (`9f67ced`) e
`working_tree_dirty: true`, embora os hashes do prompt sejam diferentes. Por
isso, a comparação registra um resultado observado, mas não permite reconstruir
cada versão apenas pelo commit. Rodadas futuras devem ser feitas em worktrees
limpas e mantidas junto de seus commits.

A instrumentação e o Compose do Jaeger estão implementados, mas isso não
significa que haja um backend institucional ou retenção durável. A exigência da
Issue #61 — pelo menos 30 execuções, métricas calculadas e um SLI/SLO com valor
medido — não é alegada como concluída aqui. Da mesma forma, agentes Gestor e
Secretária, políticas oficiais no índice e um verificador completo continuam
como propostas, conforme o [estado da arquitetura](arquitetura.md).
