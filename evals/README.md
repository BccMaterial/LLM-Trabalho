# Golden dataset do agente

`golden_dataset.json` é o conjunto versionado da Issue #55, na versão **1.1.0**.
Ele contém 20 casos, todos com entrada, comportamento esperado, origem, classe e
justificativa. O schema formal está em `golden_dataset.schema.json`.

A versão 1.1.0 realinha as expectativas com a API atual: `dev-02` aceita
`consulta_indisponivel` quando o cadastro não existe; `dev-04` não exige
ferramentas antes da autenticação; `dev-06` restaura as quatro decisões do log
original (`edit`, `approve`, `edit`, `approve`); `dev-08` e `syn-02` pedem data e
hora exatas porque a API não devolve uma grade de horários livres; `syn-01`
aceita `informacao_insuficiente`. `syn-04` permanece como fixture parcial: o
campo de encaminhamento não existe na API usada pelo agente.

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
revalidação. O runner em `src/judge/fixtures.py` injeta essas falhas apenas nos
casos marcados, sem copiar a lógica do agente; este arquivo não finge que uma
rede indisponível ocorreu nos logs atuais.

## Limites

- Não há casos de `producao`: o projeto não possui amostra real autorizada.
- O dataset não é amostra clínica, não mede benefício para pacientes e não
  representa distribuição de atendimentos.
- Casos dos YAMLs acadêmicos que usam ferramentas ausentes, como
  `simular_estado_clinica` e `agendar_exames`, não foram incluídos como se fossem
  capacidades do agente atual.
- O dataset define critérios verificáveis; o runner com injeção de falhas
  pertence à Issue #57. As métricas de execução são registradas em `runs/` e
  consolidadas pelo comparador em `docs/evals-comparison.md`.
- Slots congelados no dataset são limpos no início de cada rodada quando já
  estão ocupados por agendamentos `Pendente` de execuções anteriores. Essa
  limpeza não apaga agendamentos com outros status nem o conflito preparado por
  `dev-09` dentro da própria rodada.
- O agente não implementa uma grade real de horários livres; a API responde
  apenas se um intervalo informado está disponível. Por isso os casos ambíguos
  esperam um pedido de data/hora exata, não uma lista de opções.

## Níveis de avaliação e juiz (Issue #56)

O mapeamento de propriedades para nível determinístico, trajetória, resultado
ou juiz LLM está em [`docs/evals.md`](../docs/evals.md). A rubrica binária e o
prompt cego são `judge_validation.json` e `judge_prompt.txt`. Os 20 rótulos e
justificativas foram revisados por Thiago Pereira Lins da Silva; `dev-08` e
`syn-10` foram reclassificados após a rodada do juiz. O registro declara que o
limiar de 17/20 foi fixado antes da rodada, cujas respostas brutas ficam em
`judge_runs/`; o commit citado, porém, não contém o arquivo do pré-registro. A
matriz final registra 18/20 acordos e classifica os dois desacordos em
`judge_validation.json`.

```bash
poetry run python scripts/validate_judge.py --dry-run
```

`--call-judge` gera uma nova rodada sem alterar o pré-registro; `--apply-run`
consolida uma rodada concluída e recalcula a matriz. Nenhum comando altera o
limiar. As saídas `syn-*` são fixtures sintéticas, não execuções do agente.
