import json
import os
from http.cookies import SimpleCookie
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from uuid import UUID

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidade",
            "description": "Consulta os agendamentos existentes na API da clínica.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_agendamento",
            "description": "Confirma um horário após a aprovação explícita do paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "professional_id": {
                        "type": "string",
                        "description": "UUID do profissional.",
                    },
                    "agenda_inicio": {
                        "type": "string",
                        "description": "Início em ISO 8601 com fuso horário.",
                    },
                    "agenda_fim": {
                        "type": "string",
                        "description": "Fim em ISO 8601 com fuso horário.",
                    },
                    "suspeita_paciente": {
                        "type": "string",
                        "description": "Descrição administrativa informada para o agendamento.",
                    },
                },
                "required": [
                    "professional_id",
                    "agenda_inicio",
                    "agenda_fim",
                    "suspeita_paciente",
                ],
                "additionalProperties": False,
            },
        },
    },
]


class ApiClient:
    def __init__(self) -> None:
        self.opener = build_opener()
        self.agent_session_cookie = ""
        self.session_cookie = ""
        self.user_session_cookie = ""
        self.authenticated_user: dict | None = None
        self.base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
        agent_email = os.getenv("API_AGENT_USER") or os.environ["API_USER"]
        agent_password = os.getenv("API_AGENT_PASSWORD") or os.environ["API_PASSWORD"]
        self._request(
            "/api/sessions",
            method="POST",
            payload={
                "email": agent_email,
                "password": agent_password,
            },
            cookie_kind="agent",
        )

    def _request(
        self,
        path: str,
        method: str = "GET",
        payload: dict | None = None,
        cookie_kind: str = "agent",
    ) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        cookie = (
            self.agent_session_cookie
            if cookie_kind == "agent"
            else self.user_session_cookie
        )
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Cookie": cookie,
            },
            method=method,
        )
        try:
            with self.opener.open(request) as response:
                cookie = SimpleCookie(response.headers.get("Set-Cookie"))
                if "session_id" in cookie:
                    session_cookie = f"session_id={cookie['session_id'].value}"
                    if cookie_kind == "agent":
                        self.agent_session_cookie = session_cookie
                        self.session_cookie = session_cookie
                    else:
                        self.user_session_cookie = session_cookie
                return json.loads(response.read().decode())
        except (HTTPError, URLError) as error:
            detail = (
                error.read().decode() if isinstance(error, HTTPError) else str(error)
            )
            raise RuntimeError(f"API indisponível ({path}): {detail}") from error

    def login_user(self, email: str, password: str) -> dict:
        result = self._request(
            "/api/sessions",
            method="POST",
            payload={"email": email, "password": password},
            cookie_kind="user",
        )
        user = result.get("user")
        if not isinstance(user, dict) or not user.get("id"):
            raise RuntimeError("A API não retornou uma identidade de usuário válida.")
        self.authenticated_user = user
        return user

    def logout_user(self) -> None:
        self.user_session_cookie = ""
        self.authenticated_user = None

    def consultar_agendamentos(self, patient_id: str | None = None) -> dict:
        if patient_id:
            patient_id = self._resolve_patient_id(patient_id)
            if not patient_id:
                return {"erro": "Paciente não encontrado na API."}
        path = "/api/appointments"
        if patient_id:
            path += f"?{urlencode({'patient_id': patient_id})}"
        return self._request(path)

    def _resolve_patient_id(self, identifier: str) -> str | None:
        try:
            UUID(identifier)
            return identifier
        except ValueError:
            pass

        users = self._request("/api/users?page_size=500").get("value", [])
        normalized_identifier = identifier.strip().casefold()
        for user in users:
            searchable_values = (
                user.get("nome"),
                user.get("username"),
                user.get("email"),
            )
            if any(
                value and value.casefold() == normalized_identifier
                for value in searchable_values
            ):
                return user["id"]
        return None

    def criar_agendamento(self, **fields: str) -> dict:
        return self._request("/api/appointments", method="POST", payload=fields)


def execute_tool(
    client: ApiClient,
    name: str,
    arguments: dict,
    authenticated_user: dict | None = None,
) -> dict:
    """Executa somente as ferramentas expostas ao modelo."""
    if name == "consultar_disponibilidade":
        return client.consultar_agendamentos()
    if name == "confirmar_agendamento":
        if not authenticated_user or not authenticated_user.get("id"):
            return {
                "erro": "authentication_required",
                "mensagem": "Faça login com /login antes de agendar.",
            }
        arguments = dict(arguments)
        arguments["patient_id"] = authenticated_user["id"]
        return client.criar_agendamento(**arguments)
    raise ValueError(f"Ferramenta desconhecida: {name}")
