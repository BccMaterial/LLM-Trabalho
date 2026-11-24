# Medição de observabilidade

Janela: coorte de todas as execuções sintéticas válidas fornecidas por versão; mínimo de 30 válidas. Faixa tarifária: paid.

## Versão issue-61

- SLI: 0.5135 (observado: 0.5135, alvo: 90%; status: missed).
- Execuções válidas: 37; excluídas: 23.
- Orçamento de erro: 18/3 falhas permitidas.
- Latência p50/p95: 1845.169/22012.471 ms.
- Custo médio estimado por execução: None USD (cobertura 89%).
- Motivos de término: {'normal_completion': 24, 'recoverable_error': 13}.
- Erros por ferramenta: {'consultar_disponibilidade': {'calls': 13, 'errors': 6, 'error_rate': 0.4615}, 'consultar_politica': {'calls': 6, 'errors': 0, 'error_rate': 0.0}, 'consultar_profissionais': {'calls': 11, 'errors': 0, 'error_rate': 0.0}}.

## Versão pr-77-final

- SLI: 0.8039 (observado: 0.8039, alvo: 90%; status: missed).
- Execuções válidas: 51; excluídas: 9.
- Orçamento de erro: 10/5 falhas permitidas.
- Latência p50/p95: 2585.454/10498.324 ms.
- Custo médio estimado por execução: None USD (cobertura 98%).
- Motivos de término: {'normal_completion': 44, 'recoverable_error': 7}.
- Erros por ferramenta: {'confirmar_agendamento': {'calls': 6, 'errors': 0, 'error_rate': 0.0}, 'consultar_disponibilidade': {'calls': 34, 'errors': 3, 'error_rate': 0.0882}, 'consultar_politica': {'calls': 9, 'errors': 0, 'error_rate': 0.0}, 'consultar_profissionais': {'calls': 31, 'errors': 0, 'error_rate': 0.0}}.

## Lacunas de evidência

- avaliacao_inconclusiva: 32
