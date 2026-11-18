# Fontes e proveniência

## Dados e regras do case

| Dado/regra | Fonte prevista | Estado |
|---|---|---|
| Usuários, profissionais e registros de agendamento da demonstração | API Flask deste repositório | Fonte de verdade apenas para registros fictícios locais; não representa integração com a clínica |
| Encaminhamento, fila clínica e horários efetivamente livres | Nenhuma integração real | Não modelados na API; o benchmark cobre esses comportamentos somente com fixtures sintéticas |
| Quantidade de quatro a seis exames e exigência de encaminhamento | Material público e premissas iniciais registradas em `docs/case.md` | Contexto acadêmico, não política operacional verificada; não é necessário obter confirmação da clínica para concluir o protótipo |
| Critérios de prioridade | Não disponível no material público | Fora do escopo implementado; sem regra, não calcular prioridade |
| Cancelamento, remarcação e vaga liberada | Política aprovada e versionada pela clínica | Não fornecida; pedido fica pendente e não altera agenda |
| Checklist documental | Procedimento aprovado pela clínica | Não fornecido; Secretária não presume documentos além do encaminhamento já documentado |
| Resposta de disponibilidade | API de agenda consultada em tempo de execução | Não usar resposta antiga nem RAG para afirmar disponibilidade |

## Dados de avaliação

Não há dados reais de pacientes nem conjunto rotulado de prioridade no repositório. Não vamos inserir dados inventados, simular exames ou declarar métricas como se tivessem sido observadas. Antes de avaliar a priorização, a clínica precisa fornecer exemplos autorizados, minimizados/pseudonimizados e rotulados por responsável qualificado. A origem, versão da política, critérios e denominador devem acompanhar cada resultado.

Os cenários de `docs/io.md` descrevem comportamentos a verificar (agendamento, pendência documental, cancelamento sem política e prioridade sem regra); não são casos clínicos nem evidência de desempenho.

## Bibliografia

- Estratégias de chunking: [Finding the Best Chunking Strategy for Accurate AI Responses](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/)
