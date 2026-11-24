import json
import os
import random
import time
from datetime import datetime
from http.cookies import SimpleCookie
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from ...network_security import validate_service_base_url
from ..workflows.execution import (
    ApiUnavailableFailure,
    ProviderTimeoutFailure,
    remaining_seconds,
)

LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")
MAX_API_READ_ATTEMPTS = 3
API_READ_BACKOFF_SECONDS = 0.25
RETRYABLE_API_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


def _sleep_before_retry(attempt: int, attempts: int, remaining: float) -> bool:
    """Retry somente leituras idempotentes e dentro do prazo da execução."""
    if attempt >= attempts - 1:
        return False
    backoff = min(API_READ_BACKOFF_SECONDS * (2**attempt), 1.0)
    delay = backoff + random.uniform(0, backoff)
    if delay >= remaining:
        return False
    time.sleep(delay)
    return True


class ApiClient:
    def __init__(self) -> None:
        self.opener = build_opener()
        self.agent_session_cookie = ""
        self.session_cookie = ""
        self.user_session_cookie = ""
        self.authenticated_user: dict | None = None
        self.execution_deadline: str | None = None
        self.base_url = validate_service_base_url(
            os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/"),
            setting_name="API_BASE_URL",
        )
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
        attempts = MAX_API_READ_ATTEMPTS if method == "GET" else 1
        for attempt in range(attempts):
            timeout = remaining_seconds(self.execution_deadline)
            if timeout <= 0:
                raise ProviderTimeoutError("API excedeu o tempo máximo da execução.")
            try:
                with self.opener.open(request, timeout=timeout) as response:
                    cookie = SimpleCookie(response.headers.get("Set-Cookie"))
                    if "session_id" in cookie:
                        session_cookie = f"session_id={cookie['session_id'].value}"
                        if cookie_kind == "agent":
                            self.agent_session_cookie = session_cookie
                            self.session_cookie = session_cookie
                        else:
                            self.user_session_cookie = session_cookie
                    return json.loads(response.read().decode())
            except HTTPError as error:
                detail = error.read().decode()
                if (
                    method == "GET"
                    and error.code in RETRYABLE_API_STATUS_CODES
                    and _sleep_before_retry(attempt, attempts, timeout)
                ):
                    continue
                raise ApiUnavailableFailure(
                    f"API indisponível ({path}): {detail}"
                ) from error
            except (URLError, TimeoutError) as error:
                if method == "GET" and _sleep_before_retry(attempt, attempts, timeout):
                    continue
                raise ApiUnavailableFailure(
                    f"API indisponível ({path}): {error}"
                ) from error

    def set_execution_deadline(self, deadline: str | None) -> None:
        self.execution_deadline = deadline

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
            response = self._request(
                f"/api/professionals/active?page={page}&page_size=500"
            )
            professionals.extend(response.get("value", []))
            if not response.get("next_link"):
                break
            page += 1
        return [
            {"id": str(professional["id"]), "nome": str(professional["nome"])}
            for professional in professionals
            if professional.get("id") and professional.get("nome")
        ]

    def consultar_agendamentos(
        self,
        professional_id: str | None = None,
        agenda_inicio: str | None = None,
        agenda_fim: str | None = None,
    ) -> dict:
        if bool(agenda_inicio) != bool(agenda_fim):
            return {
                "disponibilidade": "indeterminada",
                "motivo": "Informe o início e o fim do intervalo.",
            }
        if not professional_id or not agenda_inicio or not agenda_fim:
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
        params = urlencode(
            {
                "professional_id": professional_id,
                "agenda_inicio": agenda_inicio,
                "agenda_fim": agenda_fim,
            }
        )
        return self._request(f"/api/appointments/availability?{params}")

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
        return parsed

    def criar_agendamento(self, **fields: str) -> dict:
        payload = dict(fields)
        for field in ("agenda_inicio", "agenda_fim"):
            value = payload.get(field)
            if value is not None:
                payload[field] = self._parse_iso_datetime(value).isoformat()
        return self._request(
            "/api/appointments",
            method="POST",
            payload=payload,
            cookie_kind="user",
        )
