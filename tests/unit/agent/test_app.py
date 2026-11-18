import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from langgraph.types import Command

from src.agent.workflows.execution import (
    LANGGRAPH_RECURSION_LIMIT,
    MAX_EXTERNAL_CALLS,
    MAX_MODEL_TOKENS,
    MAX_WORKFLOW_STEPS,
    TerminationReason,
    new_execution_deadline,
)
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
        "completed_actions": {},
        "approval_expires_at": None,
        "professional_name": None,
        "professional_validated": False,
        "execution_deadline": new_execution_deadline(),
        "workflow_step_count": 0,
        "external_call_count": 0,
        "total_model_tokens": 0,
        "tool_call_counts": {},
        "termination_reason": None,
        "error_class": None,
    }


def _config():
    return {
        "configurable": {"thread_id": "conversation-1"},
        "recursion_limit": LANGGRAPH_RECURSION_LIMIT,
    }


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


def _response(message, usage_tokens=0):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(total_tokens=usage_tokens),
    )


def test_scheduling_graph_returns_model_answer(monkeypatch):
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: _response(
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
        lambda client, messages, **kwargs: next(responses),
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
        lambda client, messages, **kwargs: next(responses),
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
        lambda client, messages, **kwargs: next(responses),
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
    assert result["termination_reason"] == "action_rejected"


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
        lambda client, messages, **kwargs: next(responses),
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
        lambda client, messages, **kwargs: next(responses),
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
        lambda client, messages, **kwargs: _response(
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
        lambda client, messages, **kwargs: _response(
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
        lambda client, messages, **kwargs: _response(FakeMessage("resposta sem JSON")),
    )
    graph = build_scheduling_graph(object(), FakeApiClient())

    result = graph.invoke(_state(), _config())

    assert result["answer"] == (
        "Não consegui processar esta resposta com segurança. "
        "Pode reformular sua pergunta?"
    )


def test_scheduling_graph_does_not_repeat_an_already_applied_approved_action(
    monkeypatch,
):
    arguments = {
        "patient_id": "patient-1",
        "professional_id": "professional-1",
        "agenda_inicio": "2027-01-15T10:00:00-03:00",
        "agenda_fim": "2027-01-15T11:00:00-03:00",
        "suspeita_paciente": "Avaliação",
    }
    proposal = _response(
        FakeMessage(
            tool_calls=[
                FakeToolCall("confirmar_agendamento", arguments),
            ]
        )
    )
    responses = iter([proposal, proposal])
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: next(responses),
    )
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)

    pending = graph.invoke(
        {
            **_state(),
            "messages": _state()["messages"] + [{"role": "user", "content": "Agende."}],
        },
        _config(),
    )
    first_result = graph.invoke(Command(resume={"decision": "approve"}), _config())

    next_turn = dict(first_result)
    next_turn["messages"] = list(first_result["messages"]) + [
        {"role": "user", "content": "Tente novamente."}
    ]
    next_turn["round_count"] = 0
    next_turn["tool_results"] = []
    next_turn["workflow_step_count"] = 0
    next_turn["external_call_count"] = 0
    next_turn["total_model_tokens"] = 0
    next_turn["tool_call_counts"] = {}
    next_turn["termination_reason"] = None
    next_turn["execution_deadline"] = new_execution_deadline()
    repeated = graph.invoke(next_turn, _config())
    second_result = graph.invoke(Command(resume={"decision": "approve"}), _config())

    assert pending["__interrupt__"]
    assert repeated["__interrupt__"]
    assert len(api_client.appointments) == 1
    assert "já havia sido executada" in second_result["answer"]
    assert second_result["tool_results"][-1]["result"]["idempotent"] is True
    assert second_result["termination_reason"] == "normal_completion"


def test_scheduling_graph_expires_approval_without_booking(monkeypatch):
    start = "2027-01-15T10:00:00-03:00"
    end = "2027-01-15T11:00:00-03:00"
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: _response(
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
    api_client = FakeApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Agende."})
    pending = graph.invoke(state, _config())
    monkeypatch.setattr("src.agent.actions.deadline_expired", lambda deadline: True)

    result = graph.invoke(Command(resume={"decision": "approve"}), _config())

    assert pending["__interrupt__"]
    assert api_client.appointments == []
    assert result["termination_reason"] == "approval_expired"
    assert "expirou" in result["answer"]


def test_scheduling_graph_does_not_repeat_professional_validation_on_resume(
    monkeypatch,
):
    professional_id = "6a2609f9-e4e0-4b79-9b48-557d497ecf5f"
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: _response(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "confirmar_agendamento",
                        {
                            "professional_id": professional_id,
                            "agenda_inicio": "2027-01-15T10:00:00-03:00",
                            "agenda_fim": "2027-01-15T11:00:00-03:00",
                            "suspeita_paciente": "Avaliação",
                        },
                    )
                ]
            )
        ),
    )

    class ProfessionalApiClient(FakeApiClient):
        def __init__(self):
            super().__init__()
            self.professional_lookups = 0

        def listar_profissionais(self):
            self.professional_lookups += 1
            return [{"id": professional_id, "nome": "Profissional de teste"}]

    api_client = ProfessionalApiClient()
    graph = build_scheduling_graph(object(), api_client)
    state = _state()
    state["messages"].append({"role": "user", "content": "Agende."})

    pending = graph.invoke(state, _config())
    result = graph.invoke(Command(resume={"decision": "approve"}), _config())

    assert pending["__interrupt__"]
    assert api_client.professional_lookups == 1
    assert len(api_client.appointments) == 1
    assert result["termination_reason"] == "normal_completion"


@pytest.mark.parametrize(
    "field,value",
    [
        ("workflow_step_count", MAX_WORKFLOW_STEPS),
        ("external_call_count", MAX_EXTERNAL_CALLS),
        ("total_model_tokens", MAX_MODEL_TOKENS),
    ],
)
def test_scheduling_graph_enforces_execution_budgets_without_calling_model(
    monkeypatch,
    field,
    value,
):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("The LLM must not be called after the step limit.")

    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        unexpected_call,
    )
    state = _state()
    state[field] = value

    result = build_scheduling_graph(object(), FakeApiClient()).invoke(
        state,
        _config(),
    )

    assert result["termination_reason"] == "limit_reached"


def test_scheduling_graph_enforces_execution_deadline_without_calling_model(
    monkeypatch,
):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("The LLM must not be called after the deadline.")

    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        unexpected_call,
    )
    state = _state()
    state["execution_deadline"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()

    result = build_scheduling_graph(object(), FakeApiClient()).invoke(
        state,
        _config(),
    )

    assert result["termination_reason"] == "limit_reached"


def test_scheduling_graph_detects_repeated_read_tool_calls(monkeypatch):
    lookup = _response(FakeMessage(tool_calls=[FakeToolCall()]))
    responses = iter([lookup, lookup])
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: next(responses),
    )
    api_client = FakeApiClient()

    result = build_scheduling_graph(object(), api_client).invoke(_state(), _config())

    assert api_client.calls == ["paciente-demo"]
    assert result["termination_reason"] == "unproductive_loop"


@pytest.mark.parametrize(
    "error,reason,error_class",
    [
        (RuntimeError("temporary network error"), "recoverable_error", "recoverable"),
        (ValueError("invalid graph input"), "fatal_error", "fatal"),
    ],
)
def test_scheduling_graph_classifies_execution_errors(
    monkeypatch,
    error,
    reason,
    error_class,
):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        fail,
    )

    result = build_scheduling_graph(object(), FakeApiClient()).invoke(
        _state(), _config()
    )

    assert result["termination_reason"] == reason
    assert result["error_class"] == error_class


@pytest.mark.parametrize(
    "error,reason,error_class",
    [
        (RuntimeError("temporary API error"), "recoverable_error", "recoverable"),
        (ValueError("invalid API response"), "fatal_error", "fatal"),
    ],
)
def test_scheduling_graph_classifies_tool_errors(
    monkeypatch,
    error,
    reason,
    error_class,
):
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: _response(
            FakeMessage(tool_calls=[FakeToolCall()])
        ),
    )

    class FailingApiClient(FakeApiClient):
        def consultar_agendamentos(self, **fields):
            raise error

    result = build_scheduling_graph(object(), FailingApiClient()).invoke(
        _state(),
        _config(),
    )

    assert result["termination_reason"] == reason
    assert result["error_class"] == error_class


def test_scheduling_graph_enforces_model_token_budget(monkeypatch):
    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        lambda client, messages, **kwargs: _response(
            FakeMessage(_output("Ainda consigo responder.")),
            usage_tokens=6001,
        ),
    )

    result = build_scheduling_graph(object(), FakeApiClient()).invoke(
        _state(), _config()
    )

    assert result["termination_reason"] == "limit_reached"
    assert result["total_model_tokens"] == 6001


def test_scheduling_graph_bounds_each_model_request(monkeypatch):
    request_options = {}

    def request(client, messages, **kwargs):
        request_options.update(kwargs)
        return _response(FakeMessage(_output("Resposta segura.")))

    monkeypatch.setattr(
        "src.agent.workflows.scheduling.llm.request_with_retry",
        request,
    )

    build_scheduling_graph(object(), FakeApiClient()).invoke(_state(), _config())

    assert request_options["max_tokens"] == 1000
    assert 0 < request_options["timeout_seconds"] <= 30
