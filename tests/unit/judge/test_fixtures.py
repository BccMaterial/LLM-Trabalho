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


def test_clean_dataset_slots_removes_only_overlapping_pending_appointments():
    appointments = {
        "contaminado": {
            "status": "Pendente",
            "agenda_inicio": "2095-05-01T15:00:00+00:00",
            "agenda_fim": "2095-05-01T16:00:00+00:00",
        },
        "fora_do_slot": {
            "status": "Pendente",
            "agenda_inicio": "2095-05-01T16:00:00+00:00",
            "agenda_fim": "2095-05-01T17:00:00+00:00",
        },
        "confirmado": {
            "status": "Confirmado",
            "agenda_inicio": "2095-05-01T15:00:00+00:00",
            "agenda_fim": "2095-05-01T16:00:00+00:00",
        },
    }
    assert fixtures.clean_dataset_slots(appointments) == {"contaminado"}
