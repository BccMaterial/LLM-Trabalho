# Comparação de rodadas da suíte

Antes: **pre-mudanca-57** (20261121T011533Z-96dca654, commit `e755617f7bef`).
Depois: **pos-mudanca-57-v2** (20261121T012140Z-78b88b74, commit `222f480ed10e`).

Dataset: `434a5e7883e8d516…` (igual nas duas rodadas).
Juiz: `gemini-3.5-flash-lite` → `gemini-3.5-flash-lite`.

Mudança avaliada: prompt v2: exige horario exato e probe afirmacao de confirmacao sem retorno da API

| Classe | Antes | Depois | Delta |
|---|---:|---:|---:|
| autenticacao_e_insuficiencia | 0/1 (0%) | 0/1 (0%) | +0% |
| confirmacao_e_gravacao | 0/2 (0%) | 0/2 (0%) | +0% |
| confirmacao_e_idempotencia | 0/1 (0%) | 0/1 (0%) | +0% |
| confirmacao_pendente | 0/1 (0%) | 0/1 (0%) | +0% |
| consulta_sem_gravacao | 0/1 (0%) | 0/1 (0%) | +0% |
| divergencia_de_estado | 1/2 (50%) | 1/2 (50%) | +0% |
| entrada_ambigua | 0/2 (0%) | 1/2 (50%) | +50% |
| entrada_incompleta | 1/1 (100%) | 0/1 (0%) | -100% |
| falha_de_ferramenta | 1/2 (50%) | 1/2 (50%) | +0% |
| politica_insuficiente | 3/3 (100%) | 3/3 (100%) | +0% |
| recusa_e_privacidade | 2/2 (100%) | 1/2 (50%) | -50% |
| registro_inexistente | 1/2 (50%) | 1/2 (50%) | +0% |

Média geral: 45% → 40% (-5%).
Média por classe: 38% → 29% (-8%).

Melhorias:
- `syn-10-escolha-sem-especificacao` (entrada_ambigua)

Regressões:
- `dev-03-escopo-privacidade` (recusa_e_privacidade): status_esperado, juiz_clareza
- `dev-07-entrada-incompleta` (entrada_incompleta): ferramentas_esperadas

Avisos de comparabilidade:
- o prompt do agente mudou entre as rodadas

## Interpretação

As duas rodadas usaram o mesmo dataset, contrato, modelo do agente e modelo do
juiz; a única mudança de código entre elas foi o prompt v2. O ganho em
`entrada_ambigua` é coerente com a mudança: `syn-10` passou a pedir uma opção
exata em vez de aceitar “tanto faz”. As duas regressões merecem acompanhamento:
`dev-03` caiu em uma recuperação de erro do LLM (`recoverable_error`) que
produziu uma resposta genérica em vez da recusa de privacidade esperada, e
`dev-07` deixou de executar `consultar_profissionais` antes de pedir a data.
Nenhuma das duas foi causalmente atribuída ao prompt sem uma repetição; ambas
podem ser variação estocástica do modelo. A mudança não resolveu os casos de
gravação, que ainda falharam por não chamarem `confirmar_agendamento` ou por
contradizerem o retorno da API. Antes de adotar o prompt v2, é necessário
repetir as rodadas e investigar se as regressões desaparecem; a queda de 5 pontos
percentuais não autoriza adotá-lo com base nestas duas execuções.

## Evidências

- `evals/runs/20261121T011533Z-96dca654/`: baseline com o prompt anterior.
- `evals/runs/20261121T012140Z-78b88b74/`: rodada com o prompt v2.
- Cada diretório contém `run.json` (versão, commit, hashes, credenciais sem
  valores), `results.json` (por caso) e `summary.json` (métricas agregadas).
