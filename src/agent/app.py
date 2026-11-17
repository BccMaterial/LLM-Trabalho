import json
import os
import time
from http.cookies import SimpleCookie
from typing import Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from uuid import UUID, uuid4

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from src.prompts import load_prompt

from .demo_data import populate_example_data

load_dotenv()

ATENDENTE_PROMPT = load_prompt("atendente_v1")
SYSTEM_PROMPT = ATENDENTE_PROMPT.content
DEMO_MESSAGE = "Quero agendar uma avaliação neuropsicológica para a manhã."
MAX_TOOL_ROUNDS = 5
MAX_LLM_RETRIES = 5
RETRY_BACKOFF_SECONDS = 5
STOP_COMMANDS = {"sair", "encerrar", "fim", "quit", "exit"}
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidade",
            "description": "Consulta os agendamentos existentes na API da clínica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "ID do paciente, quando a consulta for específica.",
                    },
                },
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
                    "patient_id": {
                        "type": "string",
                        "description": "UUID do paciente.",
                    },
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
                    "patient_id",
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


class SchedulingState(TypedDict):
    messages: list[dict]
    conversation_id: str
    round_count: int
    pending_action: list[dict] | None
    approval_result: bool | None
    tool_results: list[dict[str, Any]]
    answer: str | None


class ApiClient:
    def __init__(self) -> None:
        self.opener = build_opener()
        self.session_cookie = ""
        self._request(
            "/api/sessions",
            method="POST",
            payload={
                "email": os.environ["API_USER"],
                "password": os.environ["API_PASSWORD"],
            },
        )

    def _request(
        self, path: str, method: str = "GET", payload: dict | None = None
    ) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{API_BASE_URL}{path}",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Cookie": self.session_cookie,
            },
            method=method,
        )
        try:
            with self.opener.open(request) as response:
                cookie = SimpleCookie(response.headers.get("Set-Cookie"))
                if "session_id" in cookie:
                    self.session_cookie = f"session_id={cookie['session_id'].value}"
                return json.loads(response.read().decode())
        except (HTTPError, URLError) as error:
            detail = (
                error.read().decode() if isinstance(error, HTTPError) else str(error)
            )
            raise RuntimeError(f"API indisponível ({path}): {detail}") from error

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


def execute_tool(client: ApiClient, name: str, arguments: dict) -> dict:
    """Executa somente as ferramentas expostas ao modelo."""
    if name == "consultar_disponibilidade":
        return client.consultar_agendamentos(**arguments)
    if name == "confirmar_agendamento":
        return client.criar_agendamento(**arguments)
    raise ValueError(f"Ferramenta desconhecida: {name}")


def build_scheduling_graph(llm_client: OpenAI, api_client: ApiClient):
    def call_model(state: SchedulingState) -> dict:
        response = _request_llm_with_retry(llm_client, state["messages"])
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        return {
            "messages": state["messages"] + [message.model_dump(exclude_none=True)],
            "round_count": state["round_count"] + 1,
            "pending_action": [
                tool_call.model_dump(exclude_none=True) for tool_call in tool_calls
            ]
            or None,
            "answer": None if tool_calls else message.content or "",
        }

    def route_after_model(state: SchedulingState) -> str:
        return "dispatch_tools" if state["pending_action"] else "end"

    def dispatch_tools(state: SchedulingState) -> dict:
        messages = list(state["messages"])
        tool_results = list(state["tool_results"])
        for tool_call in state["pending_action"] or []:
            name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            print(
                f"Chamada de função: {name}"
                f"({json.dumps(arguments, ensure_ascii=False)})"
            )
            result = execute_tool(api_client, name, arguments)
            print(f"Resposta da função: {json.dumps(result, ensure_ascii=False)}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
            tool_results.append({"name": name, "result": result})
        return {
            "messages": messages,
            "pending_action": None,
            "tool_results": tool_results,
        }

    def route_after_tools(state: SchedulingState) -> str:
        return (
            "limit_reached" if state["round_count"] >= MAX_TOOL_ROUNDS else "call_model"
        )

    def limit_reached(_: SchedulingState) -> dict:
        return {
            "answer": (
                "Não foi possível concluir o atendimento dentro do limite "
                "da demonstração."
            )
        }

    builder = StateGraph(SchedulingState)
    builder.add_node("call_model", call_model)
    builder.add_node("dispatch_tools", dispatch_tools)
    builder.add_node("limit_reached", limit_reached)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {"dispatch_tools": "dispatch_tools", "end": END},
    )
    builder.add_conditional_edges(
        "dispatch_tools",
        route_after_tools,
        {"call_model": "call_model", "limit_reached": "limit_reached"},
    )
    builder.add_edge("limit_reached", END)
    return builder.compile()


def run_scheduling_flow(
    user_message: str = DEMO_MESSAGE, interactive: bool = True
) -> str:
    """Executa a demonstração em turnos até o paciente encerrar."""
    api_client = ApiClient()
    llm_client = OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    graph = build_scheduling_graph(llm_client, api_client)
    state: SchedulingState = {
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        "conversation_id": str(uuid4()),
        "round_count": 0,
        "pending_action": None,
        "approval_result": None,
        "tool_results": [],
        "answer": None,
    }

    while True:
        state["messages"].append({"role": "user", "content": user_message})
        state["round_count"] = 0
        state["pending_action"] = None
        print(f"\nPaciente: {user_message}")
        state = graph.invoke(state)
        answer = state["answer"] or ""
        print(f"Agente: {answer}")

        if not interactive:
            return answer

        try:
            user_message = input("\nPaciente (ou 'sair'): ").strip()
        except EOFError:
            print("\nAtendimento encerrado.")
            return answer
        if user_message.lower() in STOP_COMMANDS:
            print("Atendimento encerrado.")
            return answer
        if not user_message:
            print("Digite uma mensagem para continuar o atendimento.")
            continue


def _request_llm_with_retry(llm_client: OpenAI, messages: list[dict]):
    for attempt in range(MAX_LLM_RETRIES):
        try:
            return llm_client.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                messages=messages,
                tools=TOOLS,
            )
        except RateLimitError as error:
            if attempt == MAX_LLM_RETRIES - 1:
                raise RuntimeError(
                    f"LLM continuou limitado após {MAX_LLM_RETRIES} tentativas: "
                    f"{error.response.text}"
                ) from error

            retry_after = error.response.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else 0
            except ValueError:
                delay = 0
            delay = max(delay, RETRY_BACKOFF_SECONDS * (2**attempt))
            print(
                f"Limite do LLM atingido. Tentando novamente em {delay:g}s "
                f"({attempt + 1}/{MAX_LLM_RETRIES})..."
            )
            time.sleep(delay)
        except APIStatusError as error:
            raise RuntimeError(
                f"LLM retornou HTTP {error.status_code}: {error.response.text}"
            ) from error
        except APIConnectionError as error:
            raise RuntimeError(f"Não foi possível conectar ao LLM: {error}") from error


if __name__ == "__main__":
    print("Executando demonstração de solicitação de agendamento...")
    populate_example_data()
    print(run_scheduling_flow())
