import pytest

from src.judge import fixtures


def _case(ambiente: str) -> dict:
    return {
        "id": "syn-teste",
        "entrada": {"mensagens": ["pedido"], "ambiente": ambiente},
    }


def test_revalidation_failure_is_armed_by_approval(monkeypatch):
    monkeypatch.setattr(fixtures.ApiClient, "__init__", lambda self: None)
    monkeypatch.setattr(
        fixtures.ApiClient,
        "consultar_agendamentos",
        lambda self, **_: {"disponibilidade": "disponivel"},
    )
    with fixtures.CaseExecution(_case("falha de rede na revalidação")) as execution:
        assert (
            execution.client.consultar_agendamentos()["disponibilidade"] == "disponivel"
        )
        execution.client.arm_revalidation_failure()
        with pytest.raises(RuntimeError, match="injetada"):
            execution.client.consultar_agendamentos()


def test_consultation_failure_is_active_from_the_start(monkeypatch):
    monkeypatch.setattr(fixtures.ApiClient, "__init__", lambda self: None)
    monkeypatch.setattr(
        fixtures.ApiClient,
        "consultar_agendamentos",
        lambda self, **_: {"disponibilidade": "disponivel"},
    )
    with fixtures.CaseExecution(_case("falha de rede na consulta")) as execution:
        with pytest.raises(RuntimeError, match="injetada"):
            execution.client.consultar_agendamentos()

    assert fixtures.ApiClient.consultar_agendamentos is not None
