import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from ..network_security import validate_service_base_url

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
PATIENT_EMAIL = "paciente.demo@example.test"
PATIENT_CPF = "52998224725"
PROFESSIONAL_EMAIL = "profissional.demo@example.test"
PROFESSIONAL_CPF = "11144477735"


def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    base_url = validate_service_base_url(
        os.getenv("API_BASE_URL", API_BASE_URL).rstrip("/"),
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
        with urlopen(request) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError) as error:
        if isinstance(error, HTTPError) and error.code == 409:
            return {}
        detail = error.read().decode() if isinstance(error, HTTPError) else str(error)
        raise RuntimeError(f"Falha ao popular a API ({path}): {detail}") from error


def _find_user(email: str) -> dict:
    users = _request("/api/users?page_size=500").get("value", [])
    return next(user for user in users if user["email"] == email)


def _find_professional(email: str) -> dict:
    professionals = _request("/api/professionals?page_size=500").get("value", [])
    return next(
        professional for professional in professionals if professional["email"] == email
    )


def populate_example_data() -> None:
    """Cria, pela API, os registros mínimos usados na demonstração."""
    api_user = (os.getenv("API_AGENT_USER") or os.environ["API_USER"]).strip().lower()
    api_password = os.getenv("API_AGENT_PASSWORD") or os.environ["API_PASSWORD"]

    # A credencial usada pelo agente em runtime precisa do papel `agent`:
    # a API concede a consulta de disponibilidade somente a esse papel. A
    # semeadura usa ADMIN_API_TOKEN, então não é necessário promover o usuário
    # a `admin` (o que quebrava todas as consultas de agenda da suíte).
    _request(
        "/api/users",
        method="POST",
        payload={
            "nome": "Usuário da Demonstração",
            "username": "agente_demo",
            "cpf": "39053344705",
            "type": "agent",
            "email": api_user,
            "password": api_password,
        },
    )
    seeded_api_user = _find_user(api_user)
    _request(
        f"/api/users/{seeded_api_user['id']}",
        method="PATCH",
        payload={"type": "agent", "password": api_password},
    )
    _request(
        "/api/users",
        method="POST",
        payload={
            "nome": "Paciente da Demonstração",
            "username": "paciente_demo",
            "cpf": PATIENT_CPF,
            "type": "patient",
            "email": PATIENT_EMAIL,
            "password": "senha-paciente-demo",
        },
    )
    _request(
        "/api/professionals",
        method="POST",
        payload={
            "nome": "Dra. Profissional da Demonstração",
            "email": PROFESSIONAL_EMAIL,
            "cpf": PROFESSIONAL_CPF,
        },
    )

    patient = _find_user(PATIENT_EMAIL)
    professional = _find_professional(PROFESSIONAL_EMAIL)
    _request(
        "/api/appointments",
        method="POST",
        payload={
            "patient_id": patient["id"],
            "professional_id": professional["id"],
            "agenda_inicio": "2027-01-15T10:00:00-03:00",
            "agenda_fim": "2027-01-15T11:00:00-03:00",
            "suspeita_paciente": "Avaliação neuropsicológica de demonstração",
        },
    )
