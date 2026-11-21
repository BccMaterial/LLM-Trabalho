from src.judge.evaluate import evaluate_case


def _case(status: str = "agendamento_confirmado") -> dict:
    return {
        "id": "teste-confirmacao",
        "classe": "confirmacao_e_gravacao",
        "origem": "sintetico",
        "esperado": {
            "status": status,
            "suficiencia": (
                "suficiente" if status == "agendamento_confirmado" else "insuficiente"
            ),
            "ferramentas": ["consultar_disponibilidade", "confirmar_agendamento"],
        },
    }


def _result() -> dict:
    return {
        "structured_response": {
            "resultado": {
                "status": "agendamento_confirmado",
                "mensagem": "Agendamento confirmado.",
                "acao": "concluida",
            },
            "fonte": [{"tipo": "api", "referencia": "confirmar_agendamento"}],
            "suficiencia": "suficiente",
        },
        "tool_results": [
            {
                "name": "consultar_disponibilidade",
                "arguments": {},
                "result": {"disponibilidade": "disponivel"},
            },
            {
                "name": "confirmar_agendamento",
                "arguments": {},
                "result": {"id": "agendamento-1"},
            },
        ],
        "interrupts": [{"type": "appointment_approval"}],
    }


def test_confirmed_case_with_one_new_appointment_passes():
    record = evaluate_case(_case(), _result(), set(), {"agendamento-1"})
    assert record["passed"]
    assert not record["failed_checks"]
    assert record["checks"]["revalidacao_antes_da_escrita"] is True


def test_missing_write_is_detected_as_state_failure():
    record = evaluate_case(_case(), _result(), set(), set())
    assert not record["passed"]
    assert "efeito_estado" in record["failed_checks"]


def test_duplicate_write_is_detected():
    record = evaluate_case(
        _case(), _result(), set(), {"agendamento-1", "agendamento-2"}
    )
    assert "sem_escrita_duplicada" in record["failed_checks"]


def test_write_without_approval_and_without_revalidation_fails():
    result = _result()
    result["interrupts"] = []
    result["tool_results"] = [result["tool_results"][1]]
    record = evaluate_case(_case(), result, set(), {"agendamento-1"})
    assert "escrita_apos_aprovacao" in record["failed_checks"]
    assert "revalidacao_antes_da_escrita" in record["failed_checks"]


def test_judge_is_optional_and_idempotency_only_applies_to_designated_case():
    record = evaluate_case(_case(), _result(), set(), {"agendamento-1"})
    assert record["checks"]["juiz_clareza"] is None
    assert record["checks"]["idempotencia"] is None
    judged = evaluate_case(
        _case(), _result(), set(), {"agendamento-1"}, {"decisao": "NAO"}
    )
    assert "juiz_clareza" in judged["failed_checks"]
