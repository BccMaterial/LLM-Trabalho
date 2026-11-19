import json

import pytest
from pydantic import ValidationError

from src.agent.output_contract import AgentOutput, validate_agent_output


def _valid_payload():
    return {
        "resultado": {
            "status": "informacao_insuficiente",
            "mensagem": "Qual período você prefere?",
            "acao": "aguarda_confirmacao",
        },
        "fonte": [
            {
                "tipo": "pedido_de_clarificacao",
                "referencia": "preferencia_de_horario",
            }
        ],
        "suficiencia": "insuficiente",
    }


def _confirmed_payload():
    return {
        "resultado": {
            "status": "agendamento_confirmado",
            "mensagem": "O agendamento foi registrado.",
            "acao": "concluida",
        },
        "fonte": [
            {"tipo": "api", "referencia": "confirmar_agendamento"},
        ],
        "suficiencia": "suficiente",
    }


def test_validate_agent_output_accepts_a_consistent_response():
    output = validate_agent_output(
        json.dumps(_valid_payload(), ensure_ascii=False),
        [],
    )

    assert output.resultado.mensagem == "Qual período você prefere?"


@pytest.mark.parametrize(
    "invalid_change",
    [
        "missing_field",
        "invalid_status",
        "missing_source",
        "inconsistent_sufficiency",
    ],
)
def test_agent_output_rejects_invalid_contract_values(invalid_change):
    payload = _valid_payload()
    if invalid_change == "missing_field":
        del payload["resultado"]["mensagem"]
    elif invalid_change == "invalid_status":
        payload["resultado"]["status"] = "resposta_confirmada_sem_evidencia"
    elif invalid_change == "missing_source":
        payload["fonte"] = []
    else:
        payload["suficiencia"] = "suficiente"

    with pytest.raises(ValidationError):
        AgentOutput.model_validate(payload)


def test_agent_output_rejects_api_source_not_present_in_tool_results():
    payload = _valid_payload()
    payload["resultado"] = {
        "status": "opcoes_disponiveis",
        "mensagem": "Há horários disponíveis.",
        "acao": "aguarda_confirmacao",
    }
    payload["fonte"] = [{"tipo": "api", "referencia": "consulta_inventada"}]
    payload["suficiencia"] = "suficiente"

    with pytest.raises(ValidationError, match="não corresponde"):
        AgentOutput.model_validate(payload, context={"tool_results": []})


def test_agent_output_rejects_policy_source_not_returned_by_retrieval():
    payload = {
        "resultado": {
            "status": "revisao_humana_necessaria",
            "mensagem": "A regra exige revisão humana.",
            "acao": "encaminhada",
        },
        "fonte": [{"tipo": "politica", "referencia": "fonte_inventada"}],
        "suficiencia": "insuficiente",
    }

    with pytest.raises(ValidationError, match="trecho recuperado"):
        AgentOutput.model_validate(
            payload,
            context={
                "tool_results": [
                    {
                        "name": "consultar_politica",
                        "result": {"suficiencia": "insuficiente", "resultados": []},
                    }
                ]
            },
        )


def test_agent_output_requires_api_confirmation_before_confirmed_status():
    with pytest.raises(ValidationError, match="confirmação da API"):
        AgentOutput.model_validate(
            _confirmed_payload(),
            context={
                "tool_results": [
                    {
                        "name": "confirmar_agendamento",
                        "result": {"status": "Pendente"},
                    }
                ]
            },
        )

    output = AgentOutput.model_validate(
        _confirmed_payload(),
        context={
            "tool_results": [
                {
                    "name": "confirmar_agendamento",
                    "result": {"id": "appointment-1"},
                }
            ]
        },
    )

    assert output.resultado.status.value == "agendamento_confirmado"
