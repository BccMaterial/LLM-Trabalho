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
        if any(
            source.tipo == SourceType.API and source.referencia not in api_references
            for source in self.fonte
        ):
            raise ValueError(
                "A fonte da API não corresponde a um resultado disponível."
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
    except ValidationError:
        raise InvalidAgentOutputError(
            "A resposta do agente não corresponde ao contrato de saída."
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


def _get_api_references(tool_results: list[dict[str, Any]]) -> set[str]:
    references = set()
    for tool_result in tool_results:
        if tool_result["name"] not in {
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


def _has_confirmed_booking(tool_results: list[dict[str, Any]]) -> bool:
    return any(
        tool_result["name"] == "confirmar_agendamento"
        and isinstance(tool_result["result"], dict)
        and bool(tool_result["result"].get("id"))
        for tool_result in tool_results
    )
