import json

from opentelemetry.trace import Status, StatusCode

from .integrations.api import ApiClient
from .observability import mark_span_error, tracer
from .policy_retrieval import (
    MIN_POLICY_QUERY_COVERAGE,
    PolicyRetriever,
    supported_policy_results,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_profissionais",
            "description": (
                "Lista profissionais ativos e IDs reais. Use os IDs retornados "
                "em chamadas de ferramentas; nunca invente IDs. Se o paciente "
                "não escolheu um profissional, apresente os nomes e pergunte "
                "qual prefere. Nunca revele IDs ao paciente."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidade",
            "description": "Consulta os agendamentos existentes na API da clínica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "professional_id": {
                        "type": "string",
                        "description": "UUID do profissional. Opcional.",
                    },
                    "agenda_inicio": {
                        "type": "string",
                        "description": "Início do intervalo em ISO 8601. Opcional.",
                    },
                    "agenda_fim": {
                        "type": "string",
                        "description": "Fim do intervalo em ISO 8601. Opcional.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_agendamento",
            "description": "Confirma um horário após a aprovação explícita do paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "professional_id": {"type": "string"},
                    "agenda_inicio": {"type": "string"},
                    "agenda_fim": {"type": "string"},
                    "suspeita_paciente": {"type": "string"},
                },
                "required": [
                    "professional_id",
                    "agenda_inicio",
                    "agenda_fim",
                    "suspeita_paciente",
                ],
                "additionalProperties": False,
            },
        },
    },
]

POLICY_RETRIEVAL_TOOL = {
    "type": "function",
    "function": {
        "name": "consultar_politica",
        "description": (
            "Busca trechos de políticas administrativas aprovadas e vigentes. "
            "Use para responder dúvidas sobre regras da clínica; não use para "
            "consultar dados de pacientes, agenda ou disponibilidade."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "Pergunta administrativa a pesquisar no corpus.",
                },
            },
            "required": ["pergunta"],
            "additionalProperties": False,
        },
    },
}

KNOWN_TOOL_NAMES = frozenset(
    tool["function"]["name"] for tool in [*TOOLS, POLICY_RETRIEVAL_TOOL]
)


def get_tool_definitions(*, include_policy_retrieval: bool = False) -> list[dict]:
    if include_policy_retrieval:
        return [*TOOLS, POLICY_RETRIEVAL_TOOL]
    return TOOLS


def execute_tool(
    client: ApiClient,
    name: str,
    arguments: dict,
    authenticated_user: dict | None = None,
    policy_retriever: PolicyRetriever | None = None,
) -> dict:
    with tracer().start_as_current_span(
        "execute_tool",
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": name if name in KNOWN_TOOL_NAMES else "unknown",
        },
    ) as span:
        try:
            result = _execute_tool(
                client,
                name,
                arguments,
                authenticated_user=authenticated_user,
                policy_retriever=policy_retriever,
            )
        except Exception as error:
            mark_span_error(span, error)
            raise

        has_tool_error = "erro" in result
        span.set_attribute(
            "app.tool.result.status",
            "error" if has_tool_error else "success",
        )
        if has_tool_error:
            span.set_status(Status(StatusCode.ERROR))
        if name == "consultar_politica":
            references = []
            for policy in result.get("resultados", []):
                reference = [
                    policy.get("documento"),
                    policy.get("versao"),
                    policy.get("trecho"),
                ]
                if all(isinstance(part, str) and part for part in reference):
                    references.append(reference)
            span.set_attribute("app.context.policy.reference_count", len(references))
            if references:
                span.set_attribute(
                    "app.context.policy.references",
                    json.dumps(sorted(references), ensure_ascii=True),
                )
        return result


def _execute_tool(
    client: ApiClient,
    name: str,
    arguments: dict,
    authenticated_user: dict | None = None,
    policy_retriever: PolicyRetriever | None = None,
) -> dict:
    """Executa somente as ferramentas expostas ao modelo."""
    if name == "consultar_politica":
        if policy_retriever is None:
            raise ValueError("A recuperação de políticas não está configurada.")
        question = arguments["pergunta"]
        candidates = policy_retriever.search(question)
        supported_results = supported_policy_results(
            question,
            candidates,
            minimum_coverage=MIN_POLICY_QUERY_COVERAGE,
        )
        supported_chunks = {
            (result.document_id, result.version, result.chunk_id)
            for result in supported_results
        }
        return {
            "consulta": question,
            "suficiencia": "suficiente" if supported_results else "insuficiente",
            "resultados": [
                {
                    "conteudo": result.content,
                    "fonte": result.source,
                    "documento": result.document_id,
                    "versao": result.version,
                    "trecho": result.chunk_id,
                }
                for result in supported_results
            ],
            "candidatos_rejeitados": [
                {
                    "fonte": result.source,
                    "distancia": result.distance,
                }
                for result in candidates
                if (
                    result.document_id,
                    result.version,
                    result.chunk_id,
                )
                not in supported_chunks
            ],
        }
    if name == "consultar_profissionais":
        return {"value": client.listar_profissionais()}
    if name == "consultar_disponibilidade":
        allowed_arguments = {"professional_id", "agenda_inicio", "agenda_fim"}
        if set(arguments) - allowed_arguments:
            raise ValueError("A consulta de disponibilidade recebeu campos inválidos.")
        return client.consultar_agendamentos(
            professional_id=arguments.get("professional_id"),
            agenda_inicio=arguments.get("agenda_inicio"),
            agenda_fim=arguments.get("agenda_fim"),
        )
    if name == "confirmar_agendamento":
        if not authenticated_user or not authenticated_user.get("id"):
            return {
                "erro": "authentication_required",
                "mensagem": "Faça login com /login antes de agendar.",
            }
        booking_arguments = dict(arguments)
        booking_arguments["patient_id"] = authenticated_user["id"]
        try:
            return client.criar_agendamento(**booking_arguments)
        except RuntimeError as error:
            if '"status_code":409' in str(error):
                return {
                    "erro": "horario_indisponivel",
                    "mensagem": (
                        "Esse horário já está ocupado por um agendamento "
                        "pendente. Avalie outra opção."
                    ),
                }
            if '"status_code":400' in str(error):
                return {
                    "erro": "dados_invalidos",
                    "mensagem": (
                        "A API rejeitou os dados do agendamento. "
                        "Nenhum agendamento foi criado."
                    ),
                }
            raise
    raise ValueError(f"Ferramenta desconhecida: {name}")
