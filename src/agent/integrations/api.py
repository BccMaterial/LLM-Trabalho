import json
import os
from datetime import datetime
from http.cookies import SimpleCookie
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from uuid import UUID
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


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

    def listar_profissionais(self) -> list[dict[str, str]]:
        professionals = []
        page = 1
        while True:
            response = self._request(f"/api/professionals?page={page}&page_size=500")
            professionals.extend(response.get("value", []))
            if not response.get("next_link"):
                break
            page += 1
        return [
            {"id": str(professional["id"]), "nome": str(professional["nome"])}
            for professional in professionals
            if professional.get("status") is True
            and professional.get("id")
            and professional.get("nome")
        ]

    def consultar_agendamentos(
        self,
        patient_id: str | None = None,
        professional_id: str | None = None,
        agenda_inicio: str | None = None,
        agenda_fim: str | None = None,
    ) -> dict:
        if patient_id:
            patient_id = self._resolve_patient_id(patient_id)
            if not patient_id:
                return {"erro": "Paciente não encontrado na API."}
        if bool(agenda_inicio) != bool(agenda_fim):
            return {
                "disponibilidade": "indeterminada",
                "motivo": "Informe o início e o fim do intervalo.",
            }

        params: dict[str, str] = {}
        if patient_id:
            params["patient_id"] = patient_id
        if professional_id:
            params["professional_id"] = professional_id
        path = "/api/appointments"
        if params:
            path += f"?{urlencode(params)}"
        appointments = self._request(path).get("value", [])

        if not agenda_inicio or not agenda_fim:
            return {
                "disponibilidade": "indeterminada",
                "motivo": "Informe o profissional e o intervalo para avaliar.",
            }

        try:
            requested_start = self._parse_iso_datetime(agenda_inicio)
            requested_end = self._parse_iso_datetime(agenda_fim)
        except ValueError:
            return {
                "disponibilidade": "indeterminada",
                "motivo": "Formato de data ou horário inválido.",
            }
        if requested_start >= requested_end:
            return {
                "disponibilidade": "indeterminada",
                "motivo": "O início deve ser anterior ao fim.",
            }

        occupied = any(
            appointment.get("status") == "Pendente"
            and self._parse_iso_datetime(appointment["agenda_inicio"]) < requested_end
            and self._parse_iso_datetime(appointment["agenda_fim"]) > requested_start
            for appointment in appointments
            if appointment.get("agenda_inicio") and appointment.get("agenda_fim")
        )
        if occupied:
            return {
                "disponibilidade": "indisponivel",
                "motivo": "Há um agendamento pendente que ocupa o intervalo.",
            }
        return {"disponibilidade": "disponivel"}

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
        return parsed

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
        payload = dict(fields)
        for field in ("agenda_inicio", "agenda_fim"):
            value = payload.get(field)
            if value is not None:
                payload[field] = self._parse_iso_datetime(value).isoformat()
        return self._request("/api/appointments", method="POST", payload=payload)
