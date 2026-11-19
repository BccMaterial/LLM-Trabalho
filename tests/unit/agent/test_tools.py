import json
from datetime import datetime, timedelta, timezone

from src.agent import tools
from src.agent.integrations import api
from src.agent.policy_retrieval import PolicySearchResult
from src.agent.workflows.execution import MAX_EXTERNAL_CALL_SECONDS


class FakeResponse:
    def __init__(self, payload, session_cookie):
        self.payload = payload
        self.headers = {"Set-Cookie": f"session_id={session_cookie}; HttpOnly"}

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class FakeOpener:
    def __init__(self):
        self.requests = []
        self.timeouts = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if len(self.requests) == 1:
            return FakeResponse({}, "agent-session")
        return FakeResponse(
            {
                "user": {
                    "id": "authenticated-patient",
                    "email": "patient@example.test",
                }
            },
            "user-session",
        )


def test_api_client_keeps_agent_and_user_sessions_separate(monkeypatch):
    opener = FakeOpener()
    monkeypatch.setattr(api, "build_opener", lambda: opener)
    monkeypatch.setenv("API_AGENT_USER", "agent@example.test")
    monkeypatch.setenv("API_AGENT_PASSWORD", "agent-secret")

    client = tools.ApiClient()
    user = client.login_user("patient@example.test", "patient-secret")

    assert user["id"] == "authenticated-patient"
    assert client.agent_session_cookie == "session_id=agent-session"
    assert client.user_session_cookie == "session_id=user-session"
    assert opener.requests[0].headers["Cookie"] == ""
    assert all(0 < timeout <= MAX_EXTERNAL_CALL_SECONDS for timeout in opener.timeouts)


def test_api_requests_use_remaining_execution_time(monkeypatch):
    opener = FakeOpener()
    monkeypatch.setattr(api, "build_opener", lambda: opener)
    monkeypatch.setenv("API_USER", "agent@example.test")
    monkeypatch.setenv("API_PASSWORD", "agent-secret")
    client = api.ApiClient()
    client.set_execution_deadline(
        (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    )

    client._request("/api/test")

    assert 0 < opener.timeouts[-1] <= 5


def test_booking_uses_authenticated_identity_instead_of_model_id():
    class FakeClient:
        def criar_agendamento(self, **fields):
            return fields

    result = tools.execute_tool(
        FakeClient(),
        "confirmar_agendamento",
        {
            "patient_id": "patient-supplied-by-model",
            "professional_id": "professional-1",
            "agenda_inicio": "2027-01-15T10:00:00-03:00",
            "agenda_fim": "2027-01-15T11:00:00-03:00",
            "suspeita_paciente": "Avaliação",
        },
        authenticated_user={"id": "authenticated-patient"},
    )

    assert result["patient_id"] == "authenticated-patient"


def test_policy_tool_returns_only_retrieved_sources_and_sufficiency():
    class FakeRetriever:
        def search(self, question):
            assert question == "De onde pode vir o encaminhamento?"
            return [
                PolicySearchResult(
                    document_id="referrals",
                    version="v1",
                    chunk_id="section-1",
                    content="O encaminhamento pode vir de outra clínica.",
                    source="fixture://policies/referrals",
                    effective_from=datetime(2026, 1, 1).date(),
                    effective_until=None,
                    distance=0.1,
                    is_test_fixture=True,
                )
            ]

    result = tools.execute_tool(
        object(),
        "consultar_politica",
        {"pergunta": "De onde pode vir o encaminhamento?"},
        policy_retriever=FakeRetriever(),
    )

    assert result["suficiencia"] == "suficiente"
    assert result["resultados"] == [
        {
            "conteudo": "O encaminhamento pode vir de outra clínica.",
            "fonte": "fixture://policies/referrals",
            "documento": "referrals",
            "versao": "v1",
            "trecho": "section-1",
        }
    ]


def test_policy_tool_excludes_vector_candidates_without_query_support():
    class FakeRetriever:
        def search(self, question):
            return [
                PolicySearchResult(
                    document_id="booking",
                    version="v1",
                    chunk_id="section-1",
                    content=(
                        "Agendamento: grave um horário somente depois da "
                        "confirmação explícita do paciente."
                    ),
                    source="fixture://policies/booking",
                    effective_from=datetime(2026, 1, 1).date(),
                    effective_until=None,
                    distance=0.2,
                    is_test_fixture=True,
                )
            ]

    result = tools.execute_tool(
        object(),
        "consultar_politica",
        {"pergunta": "Qual prazo de diagnóstico a clínica garante?"},
        policy_retriever=FakeRetriever(),
    )

    assert result["suficiencia"] == "insuficiente"
    assert result["resultados"] == []
    assert result["candidatos_rejeitados"] == [
        {"fonte": "fixture://policies/booking", "distancia": 0.2}
    ]


def test_create_appointment_adds_sao_paulo_offset_to_naive_datetimes():
    client = api.ApiClient.__new__(api.ApiClient)
    request = {}

    def capture_request(path, method, payload):
        request.update(path=path, method=method, payload=payload)
        return payload

    client._request = capture_request

    client.criar_agendamento(
        patient_id="patient-id",
        professional_id="professional-id",
        agenda_inicio="2026-11-19T10:00:00",
        agenda_fim="2026-11-19T11:00:00",
        suspeita_paciente="Avaliação",
    )

    assert request["payload"]["agenda_inicio"] == "2026-11-19T10:00:00-03:00"
    assert request["payload"]["agenda_fim"] == "2026-11-19T11:00:00-03:00"


def test_availability_lists_all_appointments_when_patient_id_is_omitted():
    class FakeClient:
        def consultar_agendamentos(
            self,
            patient_id=None,
            professional_id=None,
            agenda_inicio=None,
            agenda_fim=None,
        ):
            return {"patient_id": patient_id}

    result = tools.execute_tool(
        FakeClient(),
        "consultar_disponibilidade",
        {},
        authenticated_user={"id": "authenticated-patient"},
    )

    assert result == {"patient_id": None}


def test_availability_accepts_optional_patient_id():
    class FakeClient:
        def consultar_agendamentos(
            self,
            patient_id=None,
            professional_id=None,
            agenda_inicio=None,
            agenda_fim=None,
        ):
            return {
                "patient_id": patient_id,
                "professional_id": professional_id,
                "agenda_inicio": agenda_inicio,
                "agenda_fim": agenda_fim,
            }

    result = tools.execute_tool(
        FakeClient(),
        "consultar_disponibilidade",
        {"patient_id": "paciente-demo"},
        authenticated_user={"id": "authenticated-patient"},
    )

    assert result["patient_id"] == "paciente-demo"


def test_availability_treats_pending_appointment_as_occupied():
    client = api.ApiClient.__new__(api.ApiClient)
    client._request = lambda path: {
        "value": [
            {
                "status": "Pendente",
                "agenda_inicio": "2027-01-15T10:00:00-03:00",
                "agenda_fim": "2027-01-15T11:00:00-03:00",
            }
        ]
    }

    result = client.consultar_agendamentos(
        professional_id="professional-1",
        agenda_inicio="2027-01-15T10:30:00-03:00",
        agenda_fim="2027-01-15T10:45:00-03:00",
    )

    assert result == {
        "disponibilidade": "indisponivel",
        "motivo": "Há um agendamento pendente que ocupa o intervalo.",
    }


def test_booking_is_blocked_without_authenticated_identity():
    class FakeClient:
        def criar_agendamento(self, **fields):
            raise AssertionError("A agendamento não deveria ser criada")

    result = tools.execute_tool(
        FakeClient(),
        "confirmar_agendamento",
        {"professional_id": "professional-1"},
        authenticated_user=None,
    )

    assert result["erro"] == "authentication_required"


def test_booking_conflict_is_returned_as_available_option_error():
    class FakeClient:
        def criar_agendamento(self, **fields):
            raise RuntimeError(
                "API indisponível (/api/appointments): "
                '{"status_code":409,"action":"The professional already '
                'has a pending appointment in this interval."}'
            )

    result = tools.execute_tool(
        FakeClient(),
        "confirmar_agendamento",
        {
            "professional_id": "professional-1",
            "agenda_inicio": "2027-01-15T10:00:00-03:00",
            "agenda_fim": "2027-01-15T11:00:00-03:00",
            "suspeita_paciente": "Avaliação",
        },
        authenticated_user={"id": "authenticated-patient"},
    )

    assert result["erro"] == "horario_indisponivel"
    assert "ocupado" in result["mensagem"]
