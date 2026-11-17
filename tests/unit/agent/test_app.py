import json
from types import SimpleNamespace

from agent.app import build_scheduling_graph


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none=True):
        message = {"role": "assistant", "tool_calls": self.tool_calls}
        if self.content is not None:
            message["content"] = self.content
        return message


class FakeToolCall:
    def __init__(
        self,
        name="consultar_disponibilidade",
        arguments=None,
    ):
        self.name = name
        self.arguments = arguments or {"patient_id": "paciente-demo"}

    def model_dump(self, exclude_none=True):
        return {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments),
            },
        }


class FakeApiClient:
    def __init__(self):
        self.calls = []
        self.appointments = []

    def consultar_agendamentos(self, patient_id=None):
        self.calls.append(patient_id)
        return {"value": [{"id": "appointment-1"}]}

    def criar_agendamento(self, **fields):
        self.appointments.append(fields)
        return {"id": "appointment-1"}


def _state():
    return {
        "messages": [{"role": "system", "content": "system prompt"}],
        "conversation_id": "conversation-1",
        "round_count": 0,
        "pending_action": None,
        "pending_message": None,
        "approval_result": None,
        "tool_results": [],
        "answer": None,
        "authenticated_user": {
            "id": "authenticated-patient",
            "email": "patient@example.test",
        },
    }


def _response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_scheduling_graph_returns_model_answer(monkeypatch):
    monkeypatch.setattr(
        "agent.app.llm.request_with_retry",
        lambda client, messages: _response(FakeMessage("Olá, como posso ajudar?")),
    )
    graph = build_scheduling_graph(object(), FakeApiClient())

    result = graph.invoke(_state())

    assert result["answer"] == "Olá, como posso ajudar?"
    assert result["round_count"] == 1
    assert result["messages"][-1]["content"] == "Olá, como posso ajudar?"


def test_scheduling_graph_dispatches_tool_without_logging_result(monkeypatch, capsys):
    responses = iter(
        [
            _response(FakeMessage(tool_calls=[FakeToolCall()])),
            _response(FakeMessage("Encontrei um agendamento.")),
        ]
    )
    monkeypatch.setattr(
        "agent.app.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)

    result = graph.invoke(_state())

    assert api_client.calls == [None]
    assert result["answer"] == "Encontrei um agendamento."
    assert result["tool_results"] == [
        {
            "name": "consultar_disponibilidade",
            "result": {"value": [{"id": "appointment-1"}]},
        }
    ]
    assert result["messages"][-2]["role"] == "tool"
    output = capsys.readouterr().out
    assert "paciente-demo" not in output
    assert "appointment-1" not in output


def test_scheduling_graph_requires_explicit_approval_before_booking(monkeypatch):
    start = "2027-01-15T10:00:00-03:00"
    end = "2027-01-15T11:00:00-03:00"
    responses = iter(
        [
            _response(
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "confirmar_agendamento",
                            {
                                "patient_id": "patient-1",
                                "professional_id": "professional-1",
                                "agenda_inicio": start,
                                "agenda_fim": end,
                                "suspeita_paciente": "dados sensíveis",
                            },
                        )
                    ]
                )
            ),
            _response(FakeMessage("O agendamento foi confirmado.")),
        ]
    )
    monkeypatch.setattr(
        "agent.app.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})

    pending = graph.invoke(state)

    assert api_client.appointments == []
    assert pending["approval_result"] is None
    assert pending["pending_action"]
    assert start in pending["answer"]
    assert end in pending["answer"]
    assert not any(message.get("tool_calls") for message in pending["messages"])

    pending["messages"].append({"role": "user", "content": "Sim, confirmo."})
    pending["round_count"] = 0
    result = graph.invoke(pending)

    assert api_client.appointments == [
        {
            "patient_id": "authenticated-patient",
            "professional_id": "professional-1",
            "agenda_inicio": start,
            "agenda_fim": end,
            "suspeita_paciente": "dados sensíveis",
        }
    ]
    assert result["answer"] == "O agendamento foi confirmado."


def test_scheduling_graph_cancels_booking_on_explicit_rejection(monkeypatch):
    responses = iter(
        [
            _response(
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "confirmar_agendamento",
                            {
                                "patient_id": "patient-1",
                                "professional_id": "professional-1",
                                "agenda_inicio": "2027-01-15T10:00:00-03:00",
                                "agenda_fim": "2027-01-15T11:00:00-03:00",
                                "suspeita_paciente": "Avaliação",
                            },
                        )
                    ]
                )
            ),
            _response(FakeMessage("Tudo bem, não farei o agendamento.")),
        ]
    )
    monkeypatch.setattr(
        "agent.app.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})
    pending = graph.invoke(state)
    pending["messages"].append({"role": "user", "content": "Não."})
    pending["round_count"] = 0

    result = graph.invoke(pending)

    assert api_client.appointments == []
    assert result["pending_action"] is None
    assert result["answer"] == "Tudo bem, não farei o agendamento."


def test_scheduling_graph_does_not_infer_approval_from_ambiguous_reply(monkeypatch):
    responses = iter(
        [
            _response(
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "confirmar_agendamento",
                            {
                                "patient_id": "patient-1",
                                "professional_id": "professional-1",
                                "agenda_inicio": "2027-01-15T10:00:00-03:00",
                                "agenda_fim": "2027-01-15T11:00:00-03:00",
                                "suspeita_paciente": "Avaliação",
                            },
                        )
                    ]
                )
            )
        ]
    )
    monkeypatch.setattr(
        "agent.app.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})
    pending = graph.invoke(state)
    pending["messages"].append({"role": "user", "content": "Talvez, preciso pensar."})
    pending["round_count"] = 0

    result = graph.invoke(pending)

    assert api_client.appointments == []
    assert result["pending_action"] is not None
    assert result["approval_result"] is None
    assert "Não consegui identificar" in result["answer"]


def test_scheduling_graph_requires_login_before_booking(monkeypatch):
    start = "2027-01-15T10:00:00-03:00"
    end = "2027-01-15T11:00:00-03:00"
    monkeypatch.setattr(
        "agent.app.llm.request_with_retry",
        lambda client, messages: _response(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "confirmar_agendamento",
                        {
                            "patient_id": "patient-supplied-by-model",
                            "professional_id": "professional-1",
                            "agenda_inicio": start,
                            "agenda_fim": end,
                            "suspeita_paciente": "Avaliação",
                        },
                    )
                ]
            )
        ),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["authenticated_user"] = None
    state["messages"].append({"role": "user", "content": "Quero agendar."})

    result = graph.invoke(state)

    assert api_client.appointments == []
    assert result["pending_action"] is None
    assert "/login" in result["answer"]
