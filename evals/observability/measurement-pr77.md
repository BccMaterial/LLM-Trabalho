# Medição de observabilidade

Janela: coorte de todas as execuções sintéticas válidas fornecidas por versão; mínimo de 30 válidas. Faixa tarifária: paid.

## Versão pr-77

- SLI: não medido (observado: 0.4118, alvo: 90%; status: insufficient_sample).
- Execuções válidas: 17; excluídas: 43.
- Orçamento de erro: 10/1 falhas permitidas.
- Latência p50/p95: 16421.928/53482.099 ms.
- Custo médio estimado por execução: None USD (cobertura 59%).
- Motivos de término: {'normal_completion': 8, 'recoverable_error': 9}.
- Erros por ferramenta: {'confirmar_agendamento': {'calls': 2, 'errors': 0, 'error_rate': 0.0}, 'consultar_disponibilidade': {'calls': 6, 'errors': 0, 'error_rate': 0.0}, 'consultar_politica': {'calls': 2, 'errors': 0, 'error_rate': 0.0}, 'consultar_profissionais': {'calls': 6, 'errors': 0, 'error_rate': 0.0}}.

## Lacunas de evidência

- avaliacao_inconclusiva: 43

## Nota sobre a rodada

Medição **parcial e não comparável ao baseline da issue #61**: 43 das 60 execuções
foram classificadas como `inconclusivo` por limite diário do provedor
(`generativelanguage.googleapis.com/generate_content_free_tier_requests`, limite
de 500 requisições/dia para `gemini-3.5-flash-lite`, com retorno estimado em
~7h). O valor observado de 0,4118 é informativo; como há apenas 17 execuções
válidas, o SLO fica `insufficient_sample` e nenhum resultado deve ser atribuído
à mudança. A medição definitiva deve repetir três rodadas no mesmo commit após
o reset da cota, com no mínimo 30 execuções válidas, sem alterar o alvo de 90%.

A taxa de erro de `consultar_disponibilidade` caiu de 46,15% no baseline para
0% nesta coorte após corrigir o papel da credencial de runtime (`agent`) na
semeadura; esse é um resultado operacional da correção, não uma substituição do
SLI. As latências p50/p95 ficaram infladas pelas tentativas adicionais de 429,
o que motivou a limitação de retry por cota diária no código atual.
