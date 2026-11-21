"""Executa o golden dataset sobre o agente real e grava uma rodada versionada."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

from src.agent.cli import run_scheduling_case
from src.judge import fixtures
from src.judge.client import judge_identity, judge_message
from src.judge.evaluate import evaluate_case
from src.judge.rubric import (
    PROMPT_PATH,
    ROOT,
    VALIDATION_PATH,
    build_prompt,
    judge_adopted,
    parse_judge_response,
    read_json,
    write_json,
)

AGENT_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
AGENT_CREDENTIALS = ("API_AGENT_USER", "API_AGENT_PASSWORD")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_info() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = "unknown", None
    return {"commit": commit, "working_tree_dirty": dirty}


def _verify_agent_env() -> None:
    missing = [name for name in AGENT_ENV if not os.environ.get(name)]
    if missing and "LLM_API_KEY" in missing and os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY foi renomeada; configure LLM_API_KEY para o agente."
        )
    if missing:
        raise RuntimeError(f"variáveis ausentes para o agente: {', '.join(missing)}")
    has_agent_user = bool(
        os.environ.get("API_AGENT_USER") and os.environ.get("API_AGENT_PASSWORD")
    )
    has_legacy_user = bool(
        os.environ.get("API_USER") and os.environ.get("API_PASSWORD")
    )
    if not (has_agent_user or has_legacy_user):
        raise RuntimeError(
            "Configure API_AGENT_USER/API_AGENT_PASSWORD (ou o fallback temporário)."
        )


def _identity(version: str, change: str, *, judge_enabled: bool) -> dict[str, Any]:
    verification = read_json(VALIDATION_PATH)
    return {
        "version": version,
        "change": change,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **_git_info(),
        "dataset": "evals/golden_dataset.json",
        "dataset_version": read_json(ROOT / "evals" / "golden_dataset.json")[
            "dataset_version"
        ],
        "dataset_sha256": _sha256_file(ROOT / "evals" / "golden_dataset.json"),
        "agent_entrypoint": "src.agent.cli.run_scheduling_case",
        "agent_model": os.environ["LLM_MODEL"],
        "agent_prompt_sha256": _sha256_file(
            ROOT / "src" / "prompts" / "atendente_v1.txt"
        ),
        "contract_sha256": _sha256_file(ROOT / "src" / "agent" / "output_contract.py"),
        "judge": judge_identity(),
        "judge_prompt_sha256": _sha256_file(PROMPT_PATH),
        "judge_validation_sha256": _sha256_file(VALIDATION_PATH),
        "judge_validation_decision": verification["decision"]["status"],
        "judge_enabled": judge_enabled,
    }


def _tool_context(result: dict) -> str:
    records = []
    for item in result.get("tool_results") or []:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "ferramenta": item.get("name"),
                "retorno": fixtures.sanitize(item.get("result")),
            }
        )
    return json.dumps(records, ensure_ascii=False, sort_keys=True)[:4000]


def _judge_case(case: dict, result: dict) -> dict | None:
    structured = result.get("structured_response")
    if not isinstance(structured, dict) or not structured.get("resultado"):
        return None
    case_for_prompt = {
        "pedido": case["entrada"]["mensagens"][-1],
        "contexto_ferramentas": _tool_context(result),
        "saida": structured,
    }
    prompt = build_prompt(case_for_prompt)
    raw = ""
    parsed = None
    for attempt in range(2):
        raw = judge_message(prompt)
        try:
            parsed = parse_judge_response(raw)
            break
        except ValueError as error:
            if attempt == 0:
                prompt += (
                    "\n\nA resposta anterior não estava no formato exigido. "
                    "Responda somente com o JSON válido, com decisao igual a SIM ou NAO."
                )
                continue
            raise RuntimeError(
                f"juiz inválido em {case['id']}; resposta bruta: {raw!r}"
            ) from error
    assert parsed is not None
    return {
        "decisao": parsed["decisao"],
        "justificativa": parsed["justificativa"],
        "criterios": parsed.get("criterios", []),
        "resposta_bruta": raw,
    }


def summarize(records: list[dict]) -> dict[str, Any]:
    by_class: dict[str, dict[str, int | float]] = {}
    by_check: dict[str, dict[str, int]] = {}
    for record in records:
        class_stats = by_class.setdefault(record["classe"], {"total": 0, "passed": 0})
        class_stats["total"] += 1
        class_stats["passed"] += int(record["passed"])
        for name, value in record["checks"].items():
            if value is None:
                continue
            stats = by_check.setdefault(name, {"aplicaveis": 0, "sucessos": 0})
            stats["aplicaveis"] += 1
            stats["sucessos"] += int(value)
    for stats in by_class.values():
        stats["taxa"] = round(stats["passed"] / stats["total"], 4)
    total = len(records)
    passed = sum(int(record["passed"]) for record in records)
    class_rates = [stats["taxa"] for stats in by_class.values()]
    return {
        "casos": total,
        "aprovados": passed,
        "media": round(passed / total, 4) if total else 0.0,
        "media_por_classe": (
            round(sum(class_rates) / len(class_rates), 4) if class_rates else 0.0
        ),
        "por_classe": by_class,
        "por_checagem": by_check,
        "juiz_avaliacoes": sum(1 for record in records if record.get("judgment")),
        "juiz_sim": sum(
            1
            for record in records
            if (record.get("judgment") or {}).get("decisao") == "SIM"
        ),
    }


def _run_case(
    case: dict,
    ids: dict[str, str],
    *,
    judge_enabled: bool,
    results_path: Path,
    records: list[dict],
) -> None:
    adapters = fixtures.case_adapters(case)
    setup, setup_ids = fixtures.case_setup(case, ids)
    before = fixtures.appointments_snapshot()
    result: dict[str, Any] = {}
    try:
        with fixtures.CaseExecution(case) as execution:
            result = run_scheduling_case(
                execution.user_messages,
                login=execution.login,
                approval_decisions=execution.decisions(ids["professional_id"]),
            )
    except Exception as error:  # a falha é evidência, não interrompe a rodada
        result = {
            "error": f"{type(error).__name__}: {error}",
            "tool_results": [],
            "interrupts": [],
            "structured_response": None,
            "answer": None,
            "termination_reason": "runner_error",
            "error_class": "fatal",
        }
    after = fixtures.appointments_snapshot()
    new_ids = fixtures.new_appointment_ids(before, after)
    fixtures.delete_appointments(new_ids | setup_ids)

    judgment = None
    if judge_enabled:
        try:
            judgment = _judge_case(case, result)
        except Exception as error:
            judgment = {
                "decisao": None,
                "justificativa": f"falha do juiz: {type(error).__name__}: {error}",
                "criterios": [],
                "resposta_bruta": "",
            }

    before_ids = set(before) | setup_ids
    record = evaluate_case(case, result, before_ids, set(after), judgment)
    record["adaptadores"] = [*adapters, *setup["adaptadores"]]
    record["answer"] = fixtures.sanitize(record.get("answer"))
    record["structured_response"] = fixtures.sanitize(record.get("structured_response"))
    record["tool_results"] = fixtures.sanitize(record.get("tool_results") or [])
    records.append(record)
    write_json(results_path, {"cases": records})
    print(
        f"{case['id']}: {'OK' if record['passed'] else 'FALHOU'} "
        f"({', '.join(record['failed_checks']) or 'todas as checagens'})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="rótulo da versão avaliada")
    parser.add_argument(
        "--change", required=True, help="descrição da mudança avaliada nesta rodada"
    )
    parser.add_argument("--output-dir", default="evals/runs")
    parser.add_argument(
        "--cases", help="IDs separados por vírgula; padrão: dataset inteiro"
    )
    parser.add_argument("--dry-run", action="store_true", help="sem chamadas externas")
    parser.add_argument(
        "--skip-judge", action="store_true", help="desativa o juiz (depuração)"
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    _verify_agent_env()
    judge_enabled = not args.skip_judge
    identity = _identity(args.version, args.change, judge_enabled=judge_enabled)
    dataset = read_json(ROOT / identity["dataset"])
    only = set(args.cases.split(",")) if args.cases else None
    selected = list(fixtures.iter_cases(dataset, only))
    if only and {case["id"] for case in selected} != only:
        unknown = sorted(only - {case["id"] for case in selected})
        parser.error(f"casos inexistentes no dataset: {', '.join(unknown)}")
    if args.dry_run:
        for case in selected:
            print(f"{case['id']}: {', '.join(fixtures.case_adapters(case)) or 'fiel'}")
        print(f"dry-run: {len(selected)} casos, nenhuma chamada externa.")
        return 0

    if judge_enabled and not judge_adopted():
        raise RuntimeError("o juiz não está adotado na validação versionada.")

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )
    run_dir = ROOT / args.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    identity["run_id"] = run_id
    identity["status"] = "em_andamento"
    write_json(run_dir / "run.json", identity)
    results_path = run_dir / "results.json"
    records: list[dict] = []

    ids = fixtures.prepare_dataset()
    for case in selected:
        _run_case(
            case,
            ids,
            judge_enabled=judge_enabled,
            results_path=results_path,
            records=records,
        )

    summary = summarize(records)
    write_json(run_dir / "summary.json", summary)
    identity["status"] = "concluida"
    write_json(run_dir / "run.json", identity)
    print(
        f"Rodada {run_id}: {summary['aprovados']}/{summary['casos']} casos "
        f"({summary['media']:.0%}). Resultados em {run_dir.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
