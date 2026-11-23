"""Adaptadores de execução do golden dataset.

O agente executado é sempre o real: ``src.agent.cli.run_scheduling_case``.
Aqui ficam apenas login de demonstração, contexto prévio, estado preparado na
API e injeção controlada de falhas de rede.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from src.agent import cli
from src.agent.demo_data import PATIENT_EMAIL, populate_example_data
from src.agent.integrations.api import ApiClient
from src.judge.rubric import ROOT
from src.network_security import validate_service_base_url

PATIENT_PASSWORD = "senha-paciente-demo"
CONFLICT_SLOT = {
    "agenda_inicio": "2091-04-23T15:00:00-03:00",
    "agenda_fim": "2091-04-23T16:00:00-03:00",
}
DATASET_SLOTS = (
    ("2095-05-01T12:00:00-03:00", "2095-05-01T13:00:00-03:00"),
    ("2093-05-10T10:00:00-03:00", "2093-05-10T11:00:00-03:00"),
    ("2090-11-20T16:00:00-03:00", "2090-11-20T17:00:00-03:00"),
    ("2098-05-27T08:00:00-03:00", "2098-05-27T09:00:00-03:00"),
    ("2098-05-28T08:00:00-03:00", "2098-05-28T09:00:00-03:00"),
    ("2091-04-23T15:00:00-03:00", "2091-04-23T16:00:00-03:00"),
    ("2027-03-19T09:00:00-03:00", "2027-03-19T10:00:00-03:00"),
)
PRIOR_CONTEXT = {
    "syn-03-confirmacao-explicita": [
        "Quero agendar a avaliação para 19 de março de 2027, das 9h às 10h. "
        "Quais horários estão disponíveis?"
    ],
    "syn-06-falha-revalidacao": [
        "Quero agendar a avaliação para 19 de março de 2027, das 9h às 10h. "
        "Quais horários estão disponíveis?"
    ],
    "syn-10-escolha-sem-especificacao": [
        "Quero agendar para 19 de março de 2027. Quais horários estão disponíveis?"
    ],
}


def _admin_request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    base_url = validate_service_base_url(
        os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/"),
        setting_name="API_BASE_URL",
    )
    request = Request(
        f"{base_url}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {os.environ['ADMIN_API_TOKEN']}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except HTTPError as error:
        if method == "DELETE" and error.code in (404, 409):
            return {}
        detail = error.read().decode()
        raise RuntimeError(f"API {method} {path} falhou: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"API indisponível em {path}: {error}") from error


def prepare_dataset() -> dict[str, str]:
    """Cria os registros sintéticos mínimos e devolve os identificadores usados."""
    load_dotenv(ROOT / ".env")
    if not os.environ.get("ADMIN_API_TOKEN"):
        raise RuntimeError("ADMIN_API_TOKEN é obrigatório para preparar a suíte.")
    populate_example_data()
    users = _admin_request("/api/users?page_size=500").get("value", [])
    professionals = _admin_request("/api/professionals?page_size=500").get("value", [])
    patient = next(item for item in users if item["email"] == PATIENT_EMAIL)
    professional = next(
        item
        for item in professionals
        if item["email"] == "profissional.demo@example.test"
    )
    return {
        "patient_id": str(patient["id"]),
        "professional_id": str(professional["id"]),
    }


def appointments_snapshot() -> dict[str, dict]:
    response = _admin_request("/api/appointments?page_size=500")
    return {
        str(item["id"]): item for item in response.get("value", []) if item.get("id")
    }


def delete_appointments(ids: set[str]) -> None:
    for appointment_id in ids:
        _admin_request(f"/api/appointments/{appointment_id}", method="DELETE")


def clean_dataset_slots(appointments: dict[str, dict]) -> set[str]:
    """Remove agendamentos pendentes que ocupem slots congelados pelo dataset."""
    slots = [
        (datetime.fromisoformat(start), datetime.fromisoformat(end))
        for start, end in DATASET_SLOTS
    ]
    cleaned: set[str] = set()
    for appointment_id, appointment in appointments.items():
        if appointment.get("status") != "Pendente":
            continue
        try:
            start = datetime.fromisoformat(appointment["agenda_inicio"])
            end = datetime.fromisoformat(appointment["agenda_fim"])
        except (KeyError, TypeError, ValueError):
            continue
        if any(start < slot_end and end > slot_start for slot_start, slot_end in slots):
            cleaned.add(appointment_id)
    return cleaned


def new_appointment_ids(before: dict[str, dict], after: dict[str, dict]) -> set[str]:
    return set(after) - set(before)


def _edit_arguments(case: dict, professional_id: str) -> dict:
    if case["id"].startswith("dev-06"):
        return {
            "professional_id": professional_id,
            "agenda_inicio": "2098-05-28T08:00:00-03:00",
            "agenda_fim": "2098-05-28T09:00:00-03:00",
            "suspeita_paciente": "Avaliação neuropsicológica de demonstração",
        }
    return {}


def case_login(case: dict) -> tuple[str, str] | None:
    if case["entrada"].get("sem_login"):
        return None
    return PATIENT_EMAIL, PATIENT_PASSWORD


def case_user_messages(case: dict) -> list[str]:
    return [
        *PRIOR_CONTEXT.get(case["id"], []),
        *case["entrada"]["mensagens"],
    ]


def case_decisions(case: dict, professional_id: str) -> list[dict]:
    decisions = deepcopy(case["entrada"].get("decisoes") or [])
    for decision in decisions:
        if decision.get("decision") == "edit" and not decision.get("arguments"):
            decision["arguments"] = _edit_arguments(case, professional_id)
    return decisions


def case_setup(case: dict, ids: dict[str, str]) -> tuple[dict, set[str]]:
    """Prepara estado na API e devolve metadados + IDs criados para limpeza."""
    if not case["id"].startswith("dev-09"):
        return {"adaptadores": []}, set()
    payload = {
        "patient_id": ids["patient_id"],
        "professional_id": ids["professional_id"],
        "suspeita_paciente": "Estado prévio da suíte de avaliação",
        **CONFLICT_SLOT,
    }
    created = _admin_request("/api/appointments", method="POST", payload=payload)
    appointment_id = str(created.get("id", ""))
    return (
        {
            "adaptadores": ["estado_preparado:conflito_dev-09"],
            "appointment_id": appointment_id,
        },
        {appointment_id} if appointment_id else set(),
    )


def case_adapters(case: dict) -> list[str]:
    adapters = []
    if case["id"] in PRIOR_CONTEXT:
        adapters.append("contexto_previo_sintetico")
    if case["entrada"].get("ambiente"):
        adapters.append("falha_de_rede_injetada")
    if case["entrada"].get("cadastro") or case["entrada"].get("politica_fixture"):
        adapters.append("fixture_parcial_sem_campo_na_api")
    if case["id"].startswith("dev-06"):
        adapters.append("argumentos_de_edicao_fornecidos_pela_fixture")
    if case["id"].startswith("dev-09"):
        adapters.append("estado_preparado:conflito_dev-09")
    return adapters


class FaultInjectingApiClient(ApiClient):
    """ApiClient real com falha de rede controlada apenas para casos marcados."""

    def __init__(
        self,
        *,
        fail_all_availability: bool = False,
        fail_availability_after_approval: bool = False,
    ) -> None:
        super().__init__()
        self.fail_all_availability = fail_all_availability
        self.fail_availability_after_approval = fail_availability_after_approval
        self._pending_revalidation_failure = False

    def arm_revalidation_failure(self) -> None:
        if self.fail_availability_after_approval:
            self._pending_revalidation_failure = True

    def consultar_agendamentos(self, **fields: Any) -> dict:
        if self.fail_all_availability or self._pending_revalidation_failure:
            self._pending_revalidation_failure = False
            raise RuntimeError("Falha de rede injetada pela suíte de avaliação.")
        return super().consultar_agendamentos(**fields)


class _GraphWithResumeHook:
    """Observa o resume de aprovação para disparar a falha na revalidação."""

    def __init__(self, graph: Any, client: FaultInjectingApiClient) -> None:
        self.graph = graph
        self.client = client

    def invoke(self, state: Any, config: dict) -> dict:
        resume = getattr(state, "resume", None)
        if isinstance(resume, dict) and resume.get("decision") == "approve":
            self.client.arm_revalidation_failure()
        return self.graph.invoke(state, config)


class CaseExecution:
    """Substitui dependências do CLI por clientes limitados ao caso, sem copiar o agente."""

    def __init__(self, case: dict) -> None:
        self.case = case
        self.client: FaultInjectingApiClient | None = None
        self._original_api: Any = None
        self._original_graph: Any = None

    def __enter__(self) -> "CaseExecution":
        environment = self.case["entrada"].get("ambiente", "")
        self.client = FaultInjectingApiClient(
            fail_all_availability="consulta" in environment,
            fail_availability_after_approval="revalidação" in environment,
        )
        self._original_api = cli.ApiClient
        self._original_graph = cli.build_scheduling_graph
        client = self.client

        def api_factory() -> FaultInjectingApiClient:
            return client

        def graph_factory(*args: Any, **kwargs: Any) -> Any:
            return _GraphWithResumeHook(self._original_graph(*args, **kwargs), client)

        cli.ApiClient = api_factory
        cli.build_scheduling_graph = graph_factory
        return self

    def __exit__(self, *_: Any) -> None:
        cli.ApiClient = self._original_api
        cli.build_scheduling_graph = self._original_graph

    @property
    def user_messages(self) -> list[str]:
        return case_user_messages(self.case)

    @property
    def login(self) -> tuple[str, str] | None:
        return case_login(self.case)

    def decisions(self, professional_id: str) -> list[dict]:
        return case_decisions(self.case, professional_id)


def sanitize(value: Any) -> Any:
    """Remove credenciais e identificadores antes de gravar evidências."""
    sensitive = {
        "password",
        "cookie",
        "token",
        "secret",
        "authorization",
        "patient_id",
        "id_paciente",
        "senha",
    }
    if isinstance(value, dict):
        return {
            key: "<redacted>" if str(key).casefold() in sensitive else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def iter_cases(dataset: dict, only: set[str] | None = None) -> Iterator[dict]:
    for case in dataset["cases"]:
        if only is None or case["id"] in only:
            yield case
