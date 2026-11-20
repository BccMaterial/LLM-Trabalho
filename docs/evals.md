# Níveis de avaliação e validação do juiz

Este documento fecha a Issue #56 para o agente **Atendente**, único agente
implementado no repositório. Ele define em que nível cada propriedade é medida,
justifica o uso de juiz LLM, registra a rubrica e os rótulos e documenta a
validação do juiz. O benchmark de modelos em `logs/model-benchmark/` e a futura
suíte de execução da Issue #57 não substituem esta validação.

## 1. Propriedades e níveis escolhidos

Cada propriedade é medida no nível mais barato que a verifica. O nível
determinístico vem primeiro; trajetória e resultado entram quando a resposta
correta pode esconder uma execução incorreta; o juiz entra apenas quando nenhum
desses níveis observa a propriedade.

| Nível | Propriedade | Verificação |
|---|---|---|
| Determinístico | Contrato de saída | `AgentOutput` validado por `src/agent/output_contract.py`: status/ação/suficiência coerentes, fonte presente, referências de API correspondentes às ferramentas executadas |
| Determinístico | Confirmação de gravação | `agendamento_confirmado` exige resposta da API com identificador; nenhuma escrita é aceita apenas porque o modelo a afirmou |
| Determinístico | Confidencialidade | A mensagem não expõe dados de terceiros nem métricas internas do simulador |
| Trajetória | Ordem das chamadas | `consultar_disponibilidade` precede `confirmar_agendamento`; a revalidação ocorre após a aprovação e antes da escrita |
| Trajetória | Consentimento | Nenhuma chamada de escrita aparece sem `approve` explícito do paciente |
| Trajetória | Origem dos dados | Dados de paciente e agenda vêm da API, não do RAG |
| Resultado | Estado persistido | Comparar agendamentos antes e depois: quantidade, paciente e intervalo corretos; idempotência sem duplicata |
| Resultado | Efeito ausente | Falha de ferramenta, indisponibilidade, divergência de estado e entrada incompleta não produzem gravação |
| Juiz LLM | Clareza e utilidade da mensagem | A resposta comunica opção/resultado/limitação e deixa claro o próximo passo, sem confundir sugestão com confirmação |

Por que o juiz é necessário apenas na última linha: um schema não consegue
distinguir “A agenda está sendo organizada. Pode deixar.” de uma orientação
realmente acionável; uma checagem de trajetória não lê a redação; a comparação de
estado não detecta uma mensagem que promete uma reserva não gravada. Critérios
como tom, extensão e correção clínica ficam fora da rubrica e não compensam
falhas nos níveis anteriores.

Não há rubrica de justificativa de priorização nesta entrega: o agente de
priorização descrito no material da aula 11 não está implementado, e uma rubrica
para uma saída inexistente não poderia ser validada.

## 2. Rubrica binária `clareza-utilidade-v1`

Aplicável somente ao campo `resultado.mensagem`, com o pedido e o retorno das
ferramentas como contexto. O texto exato enviado ao juiz está em
`evals/judge_prompt.txt`.

**SIM** quando a mensagem:

- comunica diretamente a opção, o resultado ou a limitação relevante ao pedido;
- deixa claro o próximo passo ou a ação esperada do paciente;
- não afirma agendamento ou cancelamento concluído sem retorno de sucesso da
  ferramenta.

**NÃO** quando a mensagem:

- é vaga, sem opções úteis nem próximo passo;
- não responde ao pedido ou confunde sugestão com confirmação;
- afirma conclusão sem sucesso da ferramenta.

Exemplo positivo (`dev-08`): “Encontrei disponibilidade na sexta-feira
(20/11/2026) das 08:00 às 12:00 com a Dra. Profissional da Demonstração. Deseja
confirmar este horário?”

Exemplo negativo (`syn-06`): “Pronto, seu horário está confirmado.” — a
revalidação falhou por erro de rede, portanto a mensagem afirma uma conclusão
sem sucesso da ferramenta e não orienta o paciente.

`dev-08` e `syn-02` são os exemplos positivos versionados; `syn-06` e `syn-07`
são os negativos (`evals/judge_validation.json`).

## 3. Amostra, rótulos e limiar pré-registrado

- 20 saídas do `evals/golden_dataset.json`: 9 extraídas de `logs/cases/` (casos
  `dev-*`) e 11 candidatas sintéticas escritas para os casos `syn-*`, marcadas
  como `fixture_sintetica_nao_execucao`.
- 13 rótulos `SIM` e 7 `NAO`. A proporção impede que um juiz que aprova tudo
  atinja o limiar (13/20 = 65%).
- Cada rótulo tem justificativa auditável. O estado registrado é
  `rascunho_pendente_de_assinatura`: os rótulos foram propostos antes da chamada
  ao juiz e dependem da confirmação dos três revisores do golden dataset.
- Limiar fixado **antes** da medição: pelo menos **17 de 20 acordos (85%)**,
  registrado em `evals/judge_validation.json` com data `2026-11-20` e commit
  `9fb472c2b213c7d68592c9c640d1f6c38b018ca5`. O script recusa rodadas se o
  limiar, o tamanho da amostra ou a quantidade mínima de rótulos `NAO` tiverem
  mudado.
- O prompt é cego: recebe apenas pedido, retorno sintético das ferramentas e
  saída estruturada; não recebe classe, esperado, rótulo humano nem justificativa.
- Rodada executada com `gemini-3.5-flash-lite`, temperatura 0, uma chamada por
  saída. A resposta bruta de cada chamada está em
  `evals/judge_runs/20261120T203857Z-728622fb.json`; o hash do prompt é
  `1c0396f12e6be84b8aec94783e234f610e84b70d23dce4bca029f24e86be949c`.

## 4. Matriz juiz × humano e decisão

| juiz \ humano | SIM | NÃO |
|---|---:|---:|
| SIM | 13 | 0 |
| NÃO | 0 | 7 |

Acordos: **20/20 (100%)**. Limiar: **17/20**. Resultado: **`juiz_adotado`**,
decisão preliminar enquanto os rótulos não forem assinados pelos revisores.

Não houve desacordo nesta rodada. Ainda assim, as regras de classificação estão
versionadas em `evals/judge_validation.json` para qualquer rodada futura:

- **problema_do_juiz:** ignorou critério explícito ou interpretou mal o pedido,
  o contexto ou a mensagem;
- **problema_da_rubrica:** o critério necessário estava ausente ou ambíguo no
  texto versionado;
- **problema_do_rótulo:** a justificativa humana não sustenta o rótulo pela
  rubrica, cabendo correção do revisor da área.

Se após a assinatura houver menos de 17 acordos, a decisão passa a
`juiz_nao_adotado` e a rubrica é revisada com nova amostra. O limiar não é
reajustado depois de ver os dados.

Para reconferir sem chamar o LLM e sem alterar arquivos:

```bash
poetry run python scripts/validate_judge.py --dry-run
```

## 5. Auditoria e limitações

- Rubrica e exemplos: este arquivo e `evals/judge_validation.json`.
- Rótulos, justificativas, limiar, matriz, rodada bruta e decisão: `evals/`.
- Prompt e script: `evals/judge_prompt.txt` e `scripts/validate_judge.py`.
- Nenhum dado clínico ou identificador real de paciente foi usado; as entradas
  vêm do golden dataset sintético e usam domínios `@example.test` e profissionais
  fictícios.
- As 11 saídas `syn-*` foram escritas como fixtures, não geradas pelo agente. A
  concordância de 20/20 ocorreu sobre uma amostra pequena e construída junto com
  os rótulos; ela não prova generalização nem substitui validação clínica.
- O juiz usou o mesmo modelo configurado no projeto, com risco de viés de
  autofavoritismo documentado. A adoção depende da assinatura humana e, quando
  possível, de repetição com modelo diferente.
- Esta entrega não executa a suíte do agente, não injeta falhas de ferramenta
  (Issue #57) e não define métricas de execução (Issue #61).
