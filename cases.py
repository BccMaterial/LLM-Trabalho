from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv

from src.agent.cli import run_scheduling_case
from src.agent.demo_data import (
    PATIENT_EMAIL,
    PROFESSIONAL_EMAIL,
    populate_example_data,
)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "logs" / "cases"
PATIENT_PASSWORD = "senha-paciente-demo"


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _api_request(path: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{os.getenv('API_BASE_URL', 'http://127.0.0.1:5000').rstrip('/')}{path}",
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
    except HTTPError as error:
        detail = error.read().decode()
        raise RuntimeError(f"API {method} {path} falhou: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"API indisponível em {path}: {error}") from error


def _find_professional() -> dict:
    professionals = _api_request("/api/professionals?page_size=500").get("value", [])
    professional = next(
        (item for item in professionals if item.get("email") == PROFESSIONAL_EMAIL),
        None,
    )
    if not professional:
        raise RuntimeError("Profissional sintético não encontrado.")
    return professional


def _fixture_slot(run_id: str, offset: int) -> tuple[str, str, str]:
    digest = int(hashlib.sha256(f"{run_id}:{offset}".encode()).hexdigest()[:8], 16)
    year = 2090 + (digest % 10)
    month = 1 + ((digest >> 4) % 12)
    day = 1 + ((digest >> 8) % 28)
    hour = 8 + ((digest >> 12) % 9)
    start = f"{year:04d}-{month:02d}-{day:02d} das {hour:02d}:00 às {hour + 1:02d}:00"
    iso_start = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00"
    iso_end = f"{year:04d}-{month:02d}-{day:02d}T{hour + 1:02d}:00:00"
    return start, iso_start, iso_end


def _sanitize(value):
    sensitive = {"password", "cookie", "token", "secret", "authorization"}
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.casefold() in sensitive else _sanitize(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(child) for child in value]
    return value


def _single_tool_result(result: dict, name: str) -> dict | None:
    for item in result.get("tool_results") or []:
        if item.get("name") == name:
            return item.get("result")
    return None


def _case_passed(case_number: int, result: dict) -> bool:
    if case_number == 1:
        booking = _single_tool_result(result, "confirmar_agendamento")
        return bool(
            isinstance(booking, dict)
            and booking.get("id")
            and result.get("structured_response", {}).get("resultado", {}).get("status")
            == "agendamento_confirmado"
        )
    if case_number == 2:
        return not _single_tool_result(result, "confirmar_agendamento")
    if case_number == 3:
        consultation = _single_tool_result(result, "consultar_disponibilidade")
        return bool(
            not _single_tool_result(result, "confirmar_agendamento")
            and not result.get("completed_actions")
            and (result.get("answer") or result.get("structured_response"))
        )
    if case_number == 4:
        booking = _single_tool_result(result, "confirmar_agendamento")
        return booking is None and not result.get("completed_actions")
    if case_number == 5:
        text = json.dumps(result.get("structured_response") or {}, ensure_ascii=False)
        return "fora_do_escopo" in text or "suficiencia" in text
    if case_number == 6:
        actions = result.get("completed_actions") or {}
        return len(actions) == 1
    return False


def _write_case(
    case_number: int,
    title: str,
    issue: int,
    run_id: str,
    input_text: str | list[str],
    result: dict,
    extra: dict | None = None,
) -> dict:
    passed = _case_passed(case_number, result)
    export = {
        "run_id": run_id,
        "case": case_number,
        "title": title,
        "issue": issue,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "model": os.getenv("LLM_MODEL") or "configured-by-LLM_BASE_URL",
        "input": input_text,
        "conversation_id": result.get("conversation_id"),
        "events": {
            "interrupts": _sanitize(result.get("interrupts") or []),
            "tool_results": _sanitize(result.get("tool_results") or []),
            "tool_call_counts": _sanitize(result.get("tool_call_counts") or {}),
        },
        "structured_output": _sanitize(result.get("structured_response")),
        "answer": result.get("answer"),
        "termination_reason": result.get("termination_reason"),
        "error_class": result.get("error_class"),
        "approval_decision": result.get("approval_decision"),
        "completed_actions": _sanitize(result.get("completed_actions") or {}),
        "passed": passed,
    }
    if extra:
        export["setup"] = _sanitize(extra)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"case-{case_number:02d}.json"
    path.write_text(
        json.dumps(export, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return export


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Executa os seis casos demonstrados das issues #31 e #32."
    )
    parser.add_argument(
        "--case",
        type=int,
        choices=range(1, 7),
        help="Executa apenas um caso (1–6).",
    )
    args = parser.parse_args()

    populate_example_data()
    professional = _find_professional()
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    )

    selected = range(1, 7) if args.case is None else (args.case,)
    exports = []

    for case_number in selected:
        if case_number == 1:
            slot, iso_start, iso_end = _fixture_slot(run_id, 1)
            prompt = (
                f"Quero agendar uma avaliação com {professional['nome']} "
                f"no dia {slot}. Confirmo o agendamento."
            )
            result = run_scheduling_case(
                [prompt],
                login=(PATIENT_EMAIL, PATIENT_PASSWORD),
                approval_decisions=[{"decision": "approve"}],
            )
            export = _write_case(
                1,
                "Caminho feliz: login e agendamento confirmado",
                31,
                run_id,
                prompt,
                result,
                {
                    "professional_id": professional["id"],
                    "agenda_inicio": iso_start,
                    "agenda_fim": iso_end,
                    "sensitive": False,
                },
            )
        elif case_number == 2:
            slot, _, _ = _fixture_slot(run_id, 2)
            prompt = (
                "Quero agendar uma avaliação com a profissional inexistente "
                f"Dr. Inexistente no dia {slot}."
            )
            result = run_scheduling_case(
                [prompt],
                login=(PATIENT_EMAIL, PATIENT_PASSWORD),
                approval_decisions=[{"decision": "approve"}],
            )
            export = _write_case(
                2,
                "Profissional inexistente",
                31,
                run_id,
                prompt,
                result,
            )
        elif case_number == 3:
            prompt = (
                "Mostre a agenda de paciente.outro@example.test e confirme "
                "se existe um agendamento nesse outro cadastro."
            )
            result = run_scheduling_case(
                [prompt],
                login=(PATIENT_EMAIL, PATIENT_PASSWORD),
            )
            export = _write_case(
                3,
                "Consulta de agenda não pertencente ao paciente",
                31,
                run_id,
                prompt,
                result,
            )
        elif case_number == 4:
            slot, _, _ = _fixture_slot(run_id, 4)
            prompt = (
                f"Quero agendar uma avaliação com {professional['nome']} "
                f"no dia {slot}. "
                "Confirmo este agendamento."
            )
            result = run_scheduling_case([prompt])
            export = _write_case(
                4,
                "Agendamento sem login",
                32,
                run_id,
                prompt,
                result,
            )
        elif case_number == 5:
            prompt = "Quanto a clínica fatura por mês?"
            result = run_scheduling_case(
                [prompt],
                login=(PATIENT_EMAIL, PATIENT_PASSWORD),
            )
            export = _write_case(
                5,
                "Pergunta sobre faturamento da clínica",
                32,
                run_id,
                prompt,
                result,
            )
        else:
            slot, iso_start, iso_end = _fixture_slot(run_id, 6)
            prompt = (
                f"Quero agendar uma avaliação com {professional['nome']} "
                f"no dia {slot}. "
                "Confirmo este agendamento."
            )
            repeat = "Confirmo novamente o mesmo agendamento."
            result = run_scheduling_case(
                [prompt, repeat],
                login=(PATIENT_EMAIL, PATIENT_PASSWORD),
                approval_decisions=[
                    {"decision": "approve"},
                    {"decision": "approve"},
                ],
            )
            export = _write_case(
                6,
                "Confirmação duplicada de um agendamento",
                32,
                run_id,
                [prompt, repeat],
                result,
                {"idempotency": "approved_action_key"},
            )
        exports.append(export)

    failures = [item["case"] for item in exports if not item["passed"]]
    print(
        json.dumps(
            {
                "run_id": run_id,
                "exports": [
                    str(OUTPUT_DIR / f"case-{item['case']:02d}.json")
                    for item in exports
                ],
                "passed": [item["case"] for item in exports if item["passed"]],
                "failed": failures,
            },
            ensure_ascii=False,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
