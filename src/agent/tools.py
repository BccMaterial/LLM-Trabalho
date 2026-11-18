from .integrations.api import ApiClient

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
                        "description": (
                            "ID, nome, username ou e-mail do paciente para "
                            "filtrar a consulta. Opcional."
                        ),
                    },
                    "professional_id": {
                        "type": "string",
                        "description": "UUID do profissional. Opcional.",
                    },
                    "agenda_inicio": {
                        "type": "string",
                        "description": "Início do intervalo em ISO 8601. Opcional.",
                    },
                    "agenda_fim": {
                        "type": "string",
                        "description": "Fim do intervalo em ISO 8601. Opcional.",
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
                    "patient_id": {"type": "string"},
                    "professional_id": {"type": "string"},
                    "agenda_inicio": {"type": "string"},
                    "agenda_fim": {"type": "string"},
                    "suspeita_paciente": {"type": "string"},
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


def execute_tool(
    client: ApiClient,
    name: str,
    arguments: dict,
    authenticated_user: dict | None = None,
) -> dict:
    """Executa somente as ferramentas expostas ao modelo."""
    if name == "consultar_disponibilidade":
        return client.consultar_agendamentos(
            patient_id=arguments.get("patient_id"),
            professional_id=arguments.get("professional_id"),
            agenda_inicio=arguments.get("agenda_inicio"),
            agenda_fim=arguments.get("agenda_fim"),
        )
    if name == "confirmar_agendamento":
        if not authenticated_user or not authenticated_user.get("id"):
            return {
                "erro": "authentication_required",
                "mensagem": "Faça login com /login antes de agendar.",
            }
        booking_arguments = dict(arguments)
        booking_arguments["patient_id"] = authenticated_user["id"]
        try:
            return client.criar_agendamento(**booking_arguments)
        except RuntimeError as error:
            if '"status_code":409' in str(error):
                return {
                    "erro": "horario_indisponivel",
                    "mensagem": (
                        "Esse horário já está ocupado por um agendamento "
                        "pendente. Avalie outra opção."
                    ),
                }
            raise
    raise ValueError(f"Ferramenta desconhecida: {name}")
