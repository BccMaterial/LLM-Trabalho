# Golden dataset do agente

`golden_dataset.json` é o conjunto versionado da Issue #55. Ele contém 20
casos, todos com entrada, comportamento esperado, origem, classe e justificativa.
O schema formal está em `golden_dataset.schema.json`.

## Proveniência e revisão

Os nove casos `dev-*` incorporam, sem duplicação artificial, as execuções
registradas nas Issues #31 e #32 em `logs/cases/`. São evidências de
**desenvolvimento** com dados de demonstração sintéticos, e não dados de
produção. Cada um preserva o `run_id`, o commit e o caminho do log.

Os onze casos `syn-*` foram construídos a partir do benchmark, do contrato em
`docs/io.md` e dos limites efetivamente implementados em `src/agent`. Foram
revisados pelos três contribuidores do projeto — Caio Troiano Collino, Thiago
Pereira Lins da Silva e Vinícius Vianna Egydio de Carvalho — quanto à entrada,
critério esperado, classe, executabilidade pelo agente atual e ausência de dados
reais. A revisão está indicada em cada caso.

O ponto de entrada pretendido para a futura suíte é
`src.agent.cli.run_scheduling_case`. Os nomes de ferramenta permitidos são os
implementados hoje: `consultar_profissionais`, `consultar_disponibilidade`,
`confirmar_agendamento` e `consultar_politica`. O contrato de saída normativo é
`src/agent/output_contract.py`; o schema antigo em `benchmarks/` não é normativo
para este dataset.

## Cobertura

O conjunto cobre confirmação e gravação, confirmação pendente, recusa e
privacidade, autenticação, entrada incompleta/ambígua, divergência de estado,
registro inexistente, política insuficiente e falhas de ferramenta. As classes
centrais de confirmação, falha de ferramenta e divergência aparecem mais de
uma vez; classes auxiliares preservam distinções úteis para cortes posteriores.

Os casos de falha de ferramenta definem falhas controladas de consulta ou
revalidação. A Issue #57 deverá fornecer o mecanismo de injeção/fixação dessas
falhas ao executar a suíte; este arquivo não finge que uma rede indisponível
ocorreu nos logs atuais.

## Limites

- Não há casos de `producao`: o projeto não possui amostra real autorizada.
- O dataset não é amostra clínica, não mede benefício para pacientes e não
  representa distribuição de atendimentos.
- Casos dos YAMLs acadêmicos que usam ferramentas ausentes, como
  `simular_estado_clinica` e `agendar_exames`, não foram incluídos como se fossem
  capacidades do agente atual.
- O dataset define critérios verificáveis; o runner com injeção de falhas
  pertence à Issue #57 e as métricas de execução à Issue #61.

## Níveis de avaliação e juiz (Issue #56)

O mapeamento de propriedades para nível determinístico, trajetória, resultado
ou juiz LLM está em [`docs/evals.md`](../docs/evals.md). A rubrica binária e o
prompt cego são `judge_validation.json` e `judge_prompt.txt`; os rótulos e
justificativas são rascunhos pendentes de assinatura dos revisores. O limiar de
17/20 foi fixado antes da rodada do juiz, cujas respostas brutas ficam em
`judge_runs/`. A matriz, as regras de classificação de desacordos e a decisão
preliminar estão em `judge_validation.json`.

```bash
poetry run python scripts/validate_judge.py --dry-run
```

`--call-judge` gera uma nova rodada sem alterar o pré-registro; `--apply-run`
consolida uma rodada concluída e recalcula a matriz. Nenhum comando altera o
limiar. As saídas `syn-*` são fixtures sintéticas, não execuções do agente.
