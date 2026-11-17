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
    def model_dump(self, exclude_none=True):
        return {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "consultar_disponibilidade",
                "arguments": '{"patient_id": "paciente-demo"}',
            },
        }


class FakeApiClient:
    def __init__(self):
        self.calls = []

    def consultar_agendamentos(self, patient_id=None):
        self.calls.append(patient_id)
        return {"value": [{"id": "appointment-1"}]}


def _state():
    return {
        "messages": [{"role": "system", "content": "system prompt"}],
        "conversation_id": "conversation-1",
        "round_count": 0,
        "pending_action": None,
        "approval_result": None,
        "tool_results": [],
        "answer": None,
    }


def _response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_scheduling_graph_returns_model_answer(monkeypatch):
    monkeypatch.setattr(
        "agent.app._request_llm_with_retry",
        lambda client, messages: _response(FakeMessage("Olá, como posso ajudar?")),
    )
    graph = build_scheduling_graph(object(), FakeApiClient())

    result = graph.invoke(_state())

    assert result["answer"] == "Olá, como posso ajudar?"
    assert result["round_count"] == 1
    assert result["messages"][-1]["content"] == "Olá, como posso ajudar?"


def test_scheduling_graph_dispatches_tool_and_returns_result(monkeypatch):
    responses = iter(
        [
            _response(FakeMessage(tool_calls=[FakeToolCall()])),
            _response(FakeMessage("Encontrei um agendamento.")),
        ]
    )
    monkeypatch.setattr(
        "agent.app._request_llm_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)

    result = graph.invoke(_state())

    assert api_client.calls == ["paciente-demo"]
    assert result["answer"] == "Encontrei um agendamento."
    assert result["tool_results"] == [
        {
            "name": "consultar_disponibilidade",
            "result": {"value": [{"id": "appointment-1"}]},
        }
    ]
    assert result["messages"][-2]["role"] == "tool"
