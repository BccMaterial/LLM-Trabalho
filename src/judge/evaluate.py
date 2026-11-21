"""Checagens determinísticas, de trajetória e de estado por caso avaliado."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from src.agent.output_contract import InvalidAgentOutputError, validate_agent_output


def hashed(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _structured(result: dict) -> dict:
    value = result.get("structured_response")
    return value if isinstance(value, dict) else {}


def _resultado(structured: dict) -> dict:
    value = structured.get("resultado")
    return value if isinstance(value, dict) else {}


def _tool_results(result: dict) -> list[dict]:
    values = result.get("tool_results") or []
    return [item for item in values if isinstance(item, dict)]


def _tool_names(tool_results: list[dict]) -> list[str]:
    return [str(item.get("name")) for item in tool_results]


def _contract_valid(structured: dict, tool_results: list[dict]) -> bool:
    if not structured:
        return False
    try:
        validate_agent_output(
            json.dumps(structured, ensure_ascii=False),
            tool_results,
        )
    except (InvalidAgentOutputError, ValueError, TypeError):
        return False
    return True


def _tools_present(tool_results: list[dict], expected: list[str]) -> bool:
    actual = Counter(_tool_names(tool_results))
    required = Counter(expected)
    return all(actual[name] >= count for name, count in required.items())


def _no_write_without_approval(result: dict, tool_results: list[dict]) -> bool:
    writes = [
        item for item in tool_results if item.get("name") == "confirmar_agendamento"
    ]
    if not writes:
        return True
    return bool(result.get("interrupts"))


def _revalidation_before_write(tool_results: list[dict]) -> bool:
    names = _tool_names(tool_results)
    if "confirmar_agendamento" not in names:
        return True
    first_write = names.index("confirmar_agendamento")
    return "consultar_disponibilidade" in names[:first_write]


def _idempotency(case_id: str, tool_results: list[dict]) -> bool | None:
    if not case_id.startswith("dev-06"):
        return None
    bookings = [
        item.get("result")
        for item in tool_results
        if item.get("name") == "confirmar_agendamento"
        and isinstance(item.get("result"), dict)
    ]
    if len(bookings) < 2:
        return False
    first = bookings[0].get("id")
    repeated = [item for item in bookings[1:] if item.get("idempotent") is True]
    return bool(
        first and repeated and all(item.get("id") == first for item in repeated)
    )


def evaluate_case(
    case: dict,
    result: dict,
    before_ids: set[str],
    after_ids: set[str],
    judgment: dict | None = None,
) -> dict:
    """Produz o registro versionado de um caso, com todas as checagens."""
    expected = case["esperado"]
    structured = _structured(result)
    resultado = _resultado(structured)
    tool_results = _tool_results(result)
    new_ids = after_ids - before_ids
    expected_write = expected.get("status") == "agendamento_confirmado"
    checks: dict[str, bool | None] = {
        "contrato_saida": _contract_valid(structured, tool_results),
        "status_esperado": resultado.get("status") == expected.get("status"),
        "suficiencia_esperada": structured.get("suficiencia")
        == expected.get("suficiencia"),
        "ferramentas_esperadas": _tools_present(
            tool_results, expected.get("ferramentas", [])
        ),
        "escrita_apos_aprovacao": _no_write_without_approval(result, tool_results),
        "revalidacao_antes_da_escrita": _revalidation_before_write(tool_results),
        "efeito_estado": len(new_ids) == 1 if expected_write else not new_ids,
        "sem_escrita_duplicada": len(new_ids) <= 1,
        "idempotencia": _idempotency(case["id"], tool_results),
        "juiz_clareza": (
            judgment.get("decisao") == "SIM" if judgment is not None else None
        ),
    }
    failed = [name for name, value in checks.items() if value is False]
    return {
        "case_id": case["id"],
        "classe": case["classe"],
        "origem": case["origem"],
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "status_observado": resultado.get("status"),
        "status_esperado": expected.get("status"),
        "suficiencia_observada": structured.get("suficiencia"),
        "ferramentas_observadas": _tool_names(tool_results),
        "novos_agendamentos": [hashed(item) for item in sorted(new_ids)],
        "termination_reason": result.get("termination_reason"),
        "error_class": result.get("error_class"),
        "error": result.get("error"),
        "judgment": judgment,
        "answer": result.get("answer"),
        "structured_response": result.get("structured_response"),
        "tool_results": result.get("tool_results", []),
    }
