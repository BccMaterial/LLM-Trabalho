import json
from types import SimpleNamespace

from langgraph.types import Command

from src.agent.workflows.scheduling import build_scheduling_graph


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

    def consultar_agendamentos(
        self,
        patient_id=None,
        professional_id=None,
        agenda_inicio=None,
        agenda_fim=None,
    ):
        self.calls.append(patient_id)
        if agenda_inicio and agenda_fim:
            return {
                "disponibilidade": "disponivel",
                "value": [],
            }
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
        "structured_response": None,
        "answer": None,
        "authenticated_user": {
            "id": "authenticated-patient",
            "email": "patient@example.test",
        },
        "approval_decision": None,
        "proposal_version": 0,
        "approved_action_key": None,
        "completed_action_keys": [],
    }


def _config():
    return {"configurable": {"thread_id": "conversation-1"}}


def _output(
    message,
    status="informacao_insuficiente",
    action="aguarda_confirmacao",
    sources=None,
    sufficiency="insuficiente",
):
    return json.dumps(
        {
            "resultado": {
                "status": status,
                "mensagem": message,
                "acao": action,
            },
            "fonte": sources
            or [
                {
                    "tipo": "pedido_de_clarificacao",
                    "referencia": "mensagem_do_paciente",
                }
            ],
            "suficiencia": sufficiency,
        },
        ensure_ascii=False,
    )


def _response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_scheduling_graph_returns_model_answer(monkeypatch):
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: _response(
            FakeMessage(_output("Olá, como posso ajudar?"))
        ),
    )
    graph = build_scheduling_graph(object(), FakeApiClient())

    result = graph.invoke(_state(), _config())

    assert result["answer"] == "Olá, como posso ajudar?"
    assert result["round_count"] == 1
    assert result["structured_response"]["resultado"]["mensagem"] == result["answer"]


def test_scheduling_graph_dispatches_tool_without_logging_result(monkeypatch, capsys):
    responses = iter(
        [
            _response(FakeMessage(tool_calls=[FakeToolCall()])),
            _response(FakeMessage(_output("Encontrei um agendamento."))),
        ]
    )
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)

    result = graph.invoke(_state(), _config())

    assert api_client.calls == ["paciente-demo"]
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
            _response(
                FakeMessage(
                    _output(
                        "O agendamento foi confirmado.",
                        status="agendamento_confirmado",
                        action="concluida",
                        sources=[
                            {
                                "tipo": "api",
                                "referencia": "confirmar_agendamento",
                            }
                        ],
                        sufficiency="suficiente",
                    )
                )
            ),
        ]
    )
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})

    pending = graph.invoke(state, _config())

    assert api_client.appointments == []
    assert pending["approval_result"] is None
    assert pending["pending_action"]
    interrupt_payload = pending["__interrupt__"][0].value
    assert start in interrupt_payload["arguments"]["agenda_inicio"]
    assert end in interrupt_payload["arguments"]["agenda_fim"]
    assert not any(message.get("tool_calls") for message in pending["messages"])

    pending["round_count"] = 0
    result = graph.invoke(Command(resume={"decision": "approve"}), _config())

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
            _response(FakeMessage(_output("Tudo bem, não farei o agendamento."))),
        ]
    )
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})
    pending = graph.invoke(state, _config())
    pending["round_count"] = 0

    result = graph.invoke(Command(resume={"decision": "reject"}), _config())

    assert api_client.appointments == []
    assert result["pending_action"] is None
    assert "recusou" in result["answer"]


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
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})
    pending = graph.invoke(state, _config())
    pending["round_count"] = 0

    result = graph.invoke(Command(resume={"decision": "invalid"}), _config())

    assert api_client.appointments == []
    assert result["pending_action"] is not None
    assert result["approval_result"] is None
    assert "Resposta inválida" in result["answer"]


def test_scheduling_graph_edits_and_repauses_before_booking(monkeypatch):
    original_start = "2027-01-15T10:00:00-03:00"
    original_end = "2027-01-15T11:00:00-03:00"
    edited_start = "2027-01-15T14:00:00-03:00"
    edited_end = "2027-01-15T15:00:00-03:00"
    responses = iter(
        [
            _response(
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "confirmar_agendamento",
                            {
                                "professional_id": "professional-1",
                                "agenda_inicio": original_start,
                                "agenda_fim": original_end,
                                "suspeita_paciente": "Avaliação",
                            },
                        )
                    ]
                )
            ),
            _response(
                FakeMessage(
                    _output(
                        "O agendamento editado foi confirmado.",
                        status="agendamento_confirmado",
                        action="concluida",
                        sources=[
                            {"tipo": "api", "referencia": "confirmar_agendamento"}
                        ],
                        sufficiency="suficiente",
                    )
                )
            ),
        ]
    )
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})

    pending = graph.invoke(state, _config())
    edited = graph.invoke(
        Command(
            resume={
                "decision": "edit",
                "arguments": {
                    "professional_id": "professional-1",
                    "agenda_inicio": edited_start,
                    "agenda_fim": edited_end,
                    "suspeita_paciente": "Avaliação atualizada",
                },
            }
        ),
        _config(),
    )

    assert api_client.appointments == []
    interrupt_payload = edited["__interrupt__"][0].value
    assert interrupt_payload["proposal_version"] == 2
    assert interrupt_payload["arguments"]["agenda_inicio"] == edited_start

    result = graph.invoke(
        Command(resume={"decision": "approve"}),
        _config(),
    )

    assert api_client.appointments == [
        {
            "patient_id": "authenticated-patient",
            "professional_id": "professional-1",
            "agenda_inicio": edited_start,
            "agenda_fim": edited_end,
            "suspeita_paciente": "Avaliação atualizada",
        }
    ]


def test_scheduling_graph_revalidates_availability_before_booking(monkeypatch):
    start = "2027-01-15T10:00:00-03:00"
    end = "2027-01-15T11:00:00-03:00"
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: _response(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "confirmar_agendamento",
                        {
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

    class UnavailableApiClient(FakeApiClient):
        def consultar_agendamentos(
            self,
            patient_id=None,
            professional_id=None,
            agenda_inicio=None,
            agenda_fim=None,
        ):
            return {
                "disponibilidade": "indisponivel",
                "motivo": "O horário acabou de ser ocupado.",
            }

    api_client = UnavailableApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Quero agendar."})
    graph.invoke(state, _config())

    result = graph.invoke(
        Command(resume={"decision": "approve"}),
        _config(),
    )

    assert api_client.appointments == []
    assert "deixou de estar disponível" in result["answer"]


def test_scheduling_graph_requires_login_before_booking(monkeypatch):
    start = "2027-01-15T10:00:00-03:00"
    end = "2027-01-15T11:00:00-03:00"
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
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

    result = graph.invoke(state, _config())

    assert api_client.appointments == []
    assert result["pending_action"] is None
    assert "/login" in result["answer"]


def test_scheduling_graph_recovers_from_invalid_final_output(monkeypatch):
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages: _response(FakeMessage("resposta sem JSON")),
    )
    graph = build_scheduling_graph(object(), FakeApiClient())

    result = graph.invoke(_state(), _config())

    assert result["answer"] == (
        "Não consegui processar esta resposta com segurança. "
        "Pode reformular sua pergunta?"
    )
