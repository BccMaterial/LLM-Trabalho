# Fontes e proveniência

## Dados e regras do case

| Dado/regra | Fonte prevista | Estado |
|---|---|---|
| Cadastro, identidade autenticada, encaminhamento, fila e agenda | API oficial da clínica | Fonte de verdade prevista; os endpoints de paciente e agenda ainda não existem neste repositório |
| Quantidade de quatro a seis exames e exigência de encaminhamento | Regras iniciais registradas em `docs/case.md` | Premissas do case acadêmico; confirmar com a clínica antes de uso real |
| Critérios de prioridade | Política aprovada e versionada pela clínica | Não fornecida; sem ela, não calcular prioridade |
| Cancelamento, remarcação e vaga liberada | Política aprovada e versionada pela clínica | Não fornecida; pedido fica pendente e não altera agenda |
| Checklist documental | Procedimento aprovado pela clínica | Não fornecido; Secretária não presume documentos além do encaminhamento já documentado |
| Resposta de disponibilidade | API de agenda consultada em tempo de execução | Não usar resposta antiga nem RAG para afirmar disponibilidade |

## Dados de avaliação

Não há dados reais de pacientes nem conjunto rotulado de prioridade no repositório. Não vamos inserir dados inventados, simular exames ou declarar métricas como se tivessem sido observadas. Antes de avaliar a priorização, a clínica precisa fornecer exemplos autorizados, minimizados/pseudonimizados e rotulados por responsável qualificado. A origem, versão da política, critérios e denominador devem acompanhar cada resultado.

Os cenários de `docs/io.md` descrevem comportamentos a verificar (agendamento, pendência documental, cancelamento sem política e prioridade sem regra); não são casos clínicos nem evidência de desempenho.

## Bibliografia

- Estratégias de chunking: [Finding the Best Chunking Strategy for Accurate AI Responses](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/)
