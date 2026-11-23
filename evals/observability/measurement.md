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

## Lacunas de evidência

- avaliacao_inconclusiva: 23
