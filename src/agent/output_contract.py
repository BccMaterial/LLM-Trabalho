from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    model_validator,
)


class OutputStatus(str, Enum):
    OPTIONS_AVAILABLE = "opcoes_disponiveis"
    APPOINTMENT_CONFIRMED = "agendamento_confirmado"
    REFERRAL_PENDING = "encaminhamento_pendente"
    REQUEST_ESCALATED = "solicitacao_encaminhada"
    HUMAN_REVIEW_REQUIRED = "revisao_humana_necessaria"
    INFORMATION_INSUFFICIENT = "informacao_insuficiente"
    API_UNAVAILABLE = "consulta_indisponivel"
    OUT_OF_SCOPE = "fora_do_escopo"
    APPOINTMENT_NOT_CONFIRMED = "agendamento_nao_confirmado"


class OutputAction(str, Enum):
    NONE = "nenhuma"
    AWAITING_CONFIRMATION = "aguarda_confirmacao"
    REFERRED = "encaminhada"
    COMPLETED = "concluida"


class SourceType(str, Enum):
    API = "api"
    POLICY = "politica"
    CLARIFICATION_REQUEST = "pedido_de_clarificacao"
    SCOPE_RULE = "regra_de_escopo"


class Sufficiency(str, Enum):
    SUFFICIENT = "suficiente"
    INSUFFICIENT = "insuficiente"


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: OutputStatus
    mensagem: str = Field(min_length=1)
    acao: OutputAction


class AgentSource(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tipo: SourceType
    referencia: str = Field(min_length=1)


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resultado: AgentResult
    fonte: list[AgentSource] = Field(min_length=1)
    suficiencia: Sufficiency

    @model_validator(mode="after")
    def validate_consistency(self, info: ValidationInfo) -> "AgentOutput":
        status = self.resultado.status
        expected_action = {
            OutputStatus.OPTIONS_AVAILABLE: OutputAction.AWAITING_CONFIRMATION,
            OutputStatus.APPOINTMENT_CONFIRMED: OutputAction.COMPLETED,
            OutputStatus.REFERRAL_PENDING: OutputAction.REFERRED,
            OutputStatus.REQUEST_ESCALATED: OutputAction.REFERRED,
            OutputStatus.HUMAN_REVIEW_REQUIRED: OutputAction.REFERRED,
            OutputStatus.INFORMATION_INSUFFICIENT: OutputAction.AWAITING_CONFIRMATION,
            OutputStatus.API_UNAVAILABLE: OutputAction.NONE,
            OutputStatus.OUT_OF_SCOPE: OutputAction.NONE,
            OutputStatus.APPOINTMENT_NOT_CONFIRMED: OutputAction.NONE,
        }[status]
        expected_sufficiency = {
            OutputStatus.OPTIONS_AVAILABLE: Sufficiency.SUFFICIENT,
            OutputStatus.APPOINTMENT_CONFIRMED: Sufficiency.SUFFICIENT,
            OutputStatus.REFERRAL_PENDING: Sufficiency.INSUFFICIENT,
            OutputStatus.REQUEST_ESCALATED: Sufficiency.INSUFFICIENT,
            OutputStatus.HUMAN_REVIEW_REQUIRED: Sufficiency.INSUFFICIENT,
            OutputStatus.INFORMATION_INSUFFICIENT: Sufficiency.INSUFFICIENT,
            OutputStatus.API_UNAVAILABLE: Sufficiency.INSUFFICIENT,
            OutputStatus.OUT_OF_SCOPE: Sufficiency.INSUFFICIENT,
            OutputStatus.APPOINTMENT_NOT_CONFIRMED: Sufficiency.INSUFFICIENT,
        }[status]
        if self.resultado.acao != expected_action:
            raise ValueError(f"A ação não é compatível com o status {status.value}.")
        if self.suficiencia != expected_sufficiency:
            raise ValueError(
                f"A suficiência não é compatível com o status {status.value}."
            )

        source_types = {source.tipo for source in self.fonte}
        required_source_types = {
            OutputStatus.OPTIONS_AVAILABLE: {SourceType.API},
            OutputStatus.APPOINTMENT_CONFIRMED: {SourceType.API},
            OutputStatus.REFERRAL_PENDING: {SourceType.API, SourceType.POLICY},
            OutputStatus.REQUEST_ESCALATED: {
                SourceType.API,
                SourceType.CLARIFICATION_REQUEST,
            },
            OutputStatus.HUMAN_REVIEW_REQUIRED: {SourceType.POLICY},
            OutputStatus.INFORMATION_INSUFFICIENT: {SourceType.CLARIFICATION_REQUEST},
            OutputStatus.API_UNAVAILABLE: {SourceType.API},
            OutputStatus.OUT_OF_SCOPE: {SourceType.SCOPE_RULE},
            OutputStatus.APPOINTMENT_NOT_CONFIRMED: {SourceType.API},
        }[status]
        if not required_source_types.issubset(source_types):
            raise ValueError(
                f"As fontes são insuficientes para o status {status.value}."
            )

        tool_results = (info.context or {}).get("tool_results", [])
        api_references = _get_api_references(tool_results)
        policy_references = _get_policy_references(tool_results)
        for source in self.fonte:
            if (
                source.tipo == SourceType.API
                and source.referencia not in api_references
            ):
                trusted_reference = _get_api_reference_for_status(
                    status,
                    tool_results,
                )
                if trusted_reference is None:
                    raise ValueError(
                        "A fonte da API não corresponde a um resultado disponível."
                    )
                source.referencia = trusted_reference
            if (
                source.tipo == SourceType.POLICY
                and source.referencia not in policy_references
            ):
                raise ValueError(
                    "A fonte da política não corresponde a um trecho recuperado."
                )

        if (
            status == OutputStatus.OPTIONS_AVAILABLE
            and not _has_available_consultation(tool_results)
        ):
            raise ValueError(
                "Opções disponíveis exigem uma consulta da API "
                "com disponibilidade confirmada."
            )

        if status == OutputStatus.APPOINTMENT_CONFIRMED and not _has_confirmed_booking(
            tool_results
        ):
            raise ValueError(
                "O status de agendamento confirmado exige confirmação da API."
            )
        return self


class InvalidAgentOutputError(ValueError):
    """Raised when a model response does not satisfy the public output contract."""


def validate_agent_output(
    content: str, tool_results: list[dict[str, Any]]
) -> AgentOutput:
    try:
        return AgentOutput.model_validate_json(
            content,
            context={"tool_results": tool_results},
        )
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or '$'}: {item['msg']}"
            for item in error.errors(include_input=False)
        )
        raise InvalidAgentOutputError(
            "A resposta do agente não corresponde ao contrato de saída. "
            f"Conteúdo retornado pelo LLM: {content!r}. "
            f"Detalhes da validação: {details}"
        ) from None


def insufficient_response(message: str, reference: str) -> AgentOutput:
    return AgentOutput(
        resultado={
            "status": OutputStatus.INFORMATION_INSUFFICIENT,
            "mensagem": message,
            "acao": OutputAction.AWAITING_CONFIRMATION,
        },
        fonte=[
            {
                "tipo": SourceType.CLARIFICATION_REQUEST,
                "referencia": reference,
            }
        ],
        suficiencia=Sufficiency.INSUFFICIENT,
    )


def api_unavailable_response(
    message: str,
    reference: str,
    tool_results: list[dict[str, Any]] | None = None,
) -> AgentOutput:
    """Saída para falha de consulta, com fonte de API rastreável."""
    return AgentOutput.model_validate(
        {
            "resultado": {
                "status": OutputStatus.API_UNAVAILABLE,
                "mensagem": message,
                "acao": OutputAction.NONE,
            },
            "fonte": [{"tipo": SourceType.API, "referencia": reference}],
            "suficiencia": Sufficiency.INSUFFICIENT,
        },
        context={"tool_results": tool_results or []},
    )


def booking_result_response(
    tool_results: list[dict[str, Any]],
) -> AgentOutput | None:
    booking_tool_result = next(
        (
            tool_result
            for tool_result in reversed(tool_results)
            if tool_result["name"] == "confirmar_agendamento"
        ),
        None,
    )
    if booking_tool_result is None:
        return None

    result = booking_tool_result["result"]
    if not isinstance(result, dict):
        return None

    if result.get("id"):
        start = result.get("agenda_inicio")
        end = result.get("agenda_fim")
        if result.get("idempotent"):
            message = (
                "Esta ação já havia sido executada; o agendamento existente "
                "foi mantido."
            )
        else:
            message = (
                f"O agendamento foi confirmado para {start} a {end}."
                if start and end
                else "O agendamento foi confirmado."
            )
        status = OutputStatus.APPOINTMENT_CONFIRMED
        action = OutputAction.COMPLETED
        sufficiency = Sufficiency.SUFFICIENT
    else:
        if result.get("erro") == "horario_indisponivel":
            message = (
                "O horário não está mais disponível. Nenhum agendamento foi "
                "criado; escolha outro horário para continuar."
            )
        elif result.get("erro") == "dados_invalidos":
            message = (
                "A API rejeitou os dados do agendamento. Nenhum agendamento "
                "foi criado; revise os dados com a equipe da clínica."
            )
        else:
            message = (
                "A API não confirmou o agendamento. Nenhum agendamento foi "
                "criado; confirme os dados antes de tentar novamente."
            )
        status = OutputStatus.APPOINTMENT_NOT_CONFIRMED
        action = OutputAction.NONE
        sufficiency = Sufficiency.INSUFFICIENT

    return AgentOutput.model_validate(
        {
            "resultado": {
                "status": status,
                "mensagem": message,
                "acao": action,
            },
            "fonte": [
                {
                    "tipo": SourceType.API,
                    "referencia": "confirmar_agendamento",
                }
            ],
            "suficiencia": sufficiency,
        },
        context={"tool_results": tool_results},
    )


def _get_api_references(tool_results: list[dict[str, Any]]) -> set[str]:
    references = set()
    for tool_result in tool_results:
        if tool_result["name"] not in {
            "consultar_profissionais",
            "consultar_disponibilidade",
            "confirmar_agendamento",
        }:
            continue
        references.add(tool_result["name"])
        result = tool_result["result"]
        if not isinstance(result, dict):
            continue
        if result.get("id") is not None:
            references.add(str(result["id"]))
        records = result.get("value", [])
        if isinstance(records, list):
            references.update(
                str(record["id"])
                for record in records
                if isinstance(record, dict) and record.get("id") is not None
            )
    return references


def _get_policy_references(tool_results: list[dict[str, Any]]) -> set[str]:
    references = set()
    for tool_result in tool_results:
        if tool_result["name"] != "consultar_politica":
            continue
        result = tool_result["result"]
        if not isinstance(result, dict):
            continue
        chunks = result.get("resultados", [])
        if isinstance(chunks, list):
            references.update(
                chunk["fonte"]
                for chunk in chunks
                if isinstance(chunk, dict) and isinstance(chunk.get("fonte"), str)
            )
    return references


def _has_available_consultation(tool_results: list[dict[str, Any]]) -> bool:
    return any(
        tool_result["name"] == "consultar_disponibilidade"
        and isinstance(tool_result["result"], dict)
        and tool_result["result"].get("disponibilidade") == "disponivel"
        for tool_result in tool_results
    )


def _get_api_reference_for_status(
    status: OutputStatus,
    tool_results: list[dict[str, Any]],
) -> str | None:
    preferred_tool_names = {
        OutputStatus.OPTIONS_AVAILABLE: ("consultar_disponibilidade",),
        OutputStatus.APPOINTMENT_CONFIRMED: ("confirmar_agendamento",),
        OutputStatus.APPOINTMENT_NOT_CONFIRMED: (
            "confirmar_agendamento",
            "consultar_disponibilidade",
        ),
    }.get(status, ())

    for preferred_name in preferred_tool_names:
        if any(result["name"] == preferred_name for result in tool_results):
            return preferred_name

    for tool_result in reversed(tool_results):
        name = tool_result["name"]
        if name in {
            "consultar_profissionais",
            "consultar_disponibilidade",
            "confirmar_agendamento",
        }:
            return name
    return None


def _has_confirmed_booking(tool_results: list[dict[str, Any]]) -> bool:
    return any(
        tool_result["name"] == "confirmar_agendamento"
        and isinstance(tool_result["result"], dict)
        and bool(tool_result["result"].get("id"))
        for tool_result in tool_results
    )
