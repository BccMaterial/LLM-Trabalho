# Comparação de rodadas da suíte

Antes: **v1-realinhado** (20261121T020151Z-eaaccc1c, commit `9f67cedf9240`).
Depois: **v2-realinhado** (20261121T020604Z-760891ad, commit `9f67cedf9240`).

Dataset: `1b73628470ed3ec3…` (igual nas duas rodadas).
Juiz: `gemini-3.5-flash-lite` → `gemini-3.5-flash-lite`.

Mudança avaliada: prompt v2 com regras explícitas de confirmação, dataset 1.1.0 e correções de reprodutibilidade

| Classe | Antes | Depois | Delta |
|---|---:|---:|---:|
| autenticacao_e_insuficiencia | 1/1 (100%) | 1/1 (100%) | +0% |
| confirmacao_e_gravacao | 2/2 (100%) | 2/2 (100%) | +0% |
| confirmacao_e_idempotencia | 1/1 (100%) | 1/1 (100%) | +0% |
| confirmacao_pendente | 1/1 (100%) | 1/1 (100%) | +0% |
| consulta_sem_gravacao | 0/1 (0%) | 1/1 (100%) | +100% |
| divergencia_de_estado | 2/2 (100%) | 1/2 (50%) | -50% |
| entrada_ambigua | 0/2 (0%) | 2/2 (100%) | +100% |
| entrada_incompleta | 0/0 (0%) | 0/1 (0%) | +0% |
| falha_de_ferramenta | 2/2 (100%) | 2/2 (100%) | +0% |
| politica_insuficiente | 3/3 (100%) | 3/3 (100%) | +0% |
| recusa_e_privacidade | 1/1 (100%) | 2/2 (100%) | +0% |
| registro_inexistente | 2/2 (100%) | 1/2 (50%) | -50% |

Média geral: 83% → 85% (+2%).
Média por classe: 82% → 83% (+2%).

Casos inconclusivos (fora do denominador): antes: `dev-07-entrada-incompleta`, `syn-08-fora-do-escopo`; depois: nenhum.

Melhorias:
- `dev-08-entrada-ambigua` (entrada_ambigua)
- `syn-02-consulta-disponibilidade` (consulta_sem_gravacao)
- `syn-10-escolha-sem-especificacao` (entrada_ambigua)

Regressões:
- `dev-02-registro-inexistente` (registro_inexistente): status_esperado
- `dev-09-divergencia-agenda` (divergencia_de_estado): juiz_clareza

Avisos de comparabilidade:
- o prompt do agente mudou entre as rodadas

## Interpretação

As rodadas `20261121T011533Z-96dca654` e `20261121T012140Z-78b88b74` foram
descartadas como evidência de qualidade: a primeira continha um agendamento
`Pendente` residual no slot de `dev-01` e ambas sofreram `429` sem classificação
de inconclusivo. Elas permanecem no histórico apenas para rastrear a execução do
comparador.

Estas duas rodadas usam o mesmo código, o mesmo dataset (`1.1.0`) e o mesmo
modelo de juiz; a única mudança entre elas é o prompt v2. A suíte limpou um slot
contaminado no início da linha de base e nenhum na segunda rodada. A linha de
base teve dois casos inconclusivos por fallback de provedor; por isso a taxa é
calculada sobre 18 casos conclusivos, não 20.

O prompt v2 venceu por 2 pontos percentuais (15/18 → 17/20) e removeu as falhas
de entrada ambígua. As duas regressões não indicaram escrita indevida: em
`dev-02` o agente reconheceu a limitação da consulta, mas classificou a saída
como `informacao_insuficiente` em vez de `consulta_indisponivel` (juiz aprovou);
em `dev-09` a revalidação detectou o conflito corretamente, mas a redação final
foi considerada vaga pelo juiz. O resultado é favorável ao prompt v2, mas ainda
não autoriza uso clínico: a API não oferece grade real de horários livres e a
suíte cobre apenas 20 casos sintéticos.

