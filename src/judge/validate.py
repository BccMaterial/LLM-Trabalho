"""Gera e confere a matriz juiz × humano da avaliação de clareza e utilidade.

O limiar e os rótulos humanos são pré-registrados em ``judge_validation.json``.
A chamada ao LLM grava respostas brutas em ``evals/judge_runs/``; nenhuma chamada
altera o limiar, os rótulos ou a decisão. ``--apply-run`` consolida uma rodada
já executada e ``--dry-run`` apenas reconfere os dados versionados.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .client import judge_identity, judge_message
from .rubric import (
    PROMPT_PATH,
    ROOT,
    RUNS_DIR,
    VALIDATION_PATH,
    build_decision,
    build_prompt,
    compute_matrix,
    normalizar_decisao,
    parse_judge_response,
    read_json,
    sha256,
    verify_pre_registration,
    write_json,
)


def call_judge() -> Path:
    identity = judge_identity()
    validation = read_json(VALIDATION_PATH)
    verify_pre_registration(validation)
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )
    path = RUNS_DIR / f"{run_id}.json"
    run: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": identity["model"],
        "provider": identity["provider"],
        "prompt_file": "evals/judge_prompt.txt",
        "prompt_sha256": sha256(prompt_text),
        "temperature": int(identity["temperature"]),
        "max_tokens": int(identity["max_tokens"]),
        "env_keys": identity["env_keys"],
        "status": "em_andamento",
        "cases": [],
    }
    write_json(path, run)

    for case in validation["cases"]:
        prompt = build_prompt(case)
        parsed = None
        raw = ""
        for attempt in range(2):
            raw = judge_message(prompt)
            try:
                parsed = parse_judge_response(raw)
                break
            except ValueError as error:
                if attempt == 0:
                    prompt = (
                        prompt
                        + "\n\nA resposta anterior não estava no formato exigido. "
                        "Responda somente com o JSON válido, com decisao igual a SIM ou NAO."
                    )
                    continue
                run["cases"].append(
                    {
                        "case_id": case["case_id"],
                        "decisao": None,
                        "justificativa": "",
                        "criterios": [],
                        "resposta_bruta": raw,
                        "erro": str(error),
                    }
                )
                write_json(path, run)
                raise RuntimeError(
                    f"juiz inválido em {case['case_id']}; resposta bruta em "
                    f"{path.relative_to(ROOT)}"
                ) from error

        assert parsed is not None
        run["cases"].append(
            {
                "case_id": case["case_id"],
                "decisao": parsed["decisao"],
                "justificativa": parsed["justificativa"],
                "criterios": parsed.get("criterios", []),
                "resposta_bruta": raw,
            }
        )
        write_json(path, run)
        print(f"{case['case_id']}: {parsed['decisao']}")

    run["status"] = "concluida"
    run["created_at"] = datetime.now(timezone.utc).isoformat()
    write_json(path, run)
    print(f"Rodada registrada em {path.relative_to(ROOT)}")
    return path


def apply_run(run_path: Path) -> None:
    validation = read_json(VALIDATION_PATH)
    verify_pre_registration(validation)
    run = read_json(run_path)
    if sha256(PROMPT_PATH.read_text(encoding="utf-8")) != run["prompt_sha256"]:
        raise ValueError("o prompt mudou desde a rodada; não é possível consolidá-la")
    if run.get("status") != "concluida":
        raise ValueError("a rodada está incompleta e não pode ser consolidada")
    if any(
        normalizar_decisao(record.get("decisao")) is None for record in run["cases"]
    ):
        raise ValueError("a rodada contém julgamento inválido")

    judgments = {record["case_id"]: record for record in run["cases"]}
    expected_ids = {case["case_id"] for case in validation["cases"]}
    if set(judgments) != expected_ids or len(run["cases"]) != len(expected_ids):
        raise ValueError("a rodada não cobre exatamente as 20 saídas pré-registradas")

    for case in validation["cases"]:
        record = judgments[case["case_id"]]
        case["juiz"] = {
            "run_id": run["run_id"],
            "decisao": normalizar_decisao(record["decisao"]),
            "justificativa": record["justificativa"],
            "criterios": record["criterios"],
        }

    run_entry = {
        "run_id": run["run_id"],
        "arquivo": str(run_path.resolve().relative_to(ROOT)),
        "model": run["model"],
        "prompt_sha256": run["prompt_sha256"],
        "temperature": run["temperature"],
    }
    if not any(item["run_id"] == run["run_id"] for item in validation["judge_runs"]):
        validation["judge_runs"].append(run_entry)

    matrix = compute_matrix(validation)
    validation["matrix"] = matrix
    validation["decision"] = build_decision(validation, matrix)
    write_json(VALIDATION_PATH, validation)
    print(
        f"Matriz: {matrix['acordos']}/{matrix['total']} acordos "
        f"({matrix['acuracia']:.0%}). Decisão: {validation['decision']['status']}"
    )


def dry_run() -> None:
    validation = read_json(VALIDATION_PATH)
    verify_pre_registration(validation)
    matrix = compute_matrix(validation)
    decision = build_decision(validation, matrix)
    problems = []
    if matrix != validation.get("matrix"):
        problems.append("matriz versionada diferente da matriz recalculada")
    if decision != validation.get("decision"):
        problems.append("decisão versionada diferente da decisão recalculada")
    disagreements = [
        case
        for case in validation["cases"]
        if case["juiz"]["decisao"] != case["humano"]["decisao"]
    ]
    classified = {item["case_id"] for item in validation["disagreements"]}
    for case in disagreements:
        if case["case_id"] not in classified:
            problems.append(f"desacordo sem classificação: {case['case_id']}")
    if problems:
        for problem in problems:
            print(f"ERRO: {problem}", file=sys.stderr)
        raise SystemExit(1)
    print(
        f"OK: {matrix['acordos']}/{matrix['total']} acordos, "
        f"{len(disagreements)} desacordos classificados, decisão {decision['status']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--call-judge",
        action="store_true",
        help="chama o LLM uma vez por saída e grava respostas brutas sem alterar o pré-registro",
    )
    group.add_argument(
        "--apply-run",
        type=Path,
        help="consolida uma rodada já gravada em evals/judge_runs/",
    )
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="recalcula matriz e decisão sem chamar o LLM",
    )
    args = parser.parse_args()
    if args.call_judge:
        call_judge()
    elif args.apply_run:
        apply_run(args.apply_run)
    else:
        dry_run()


if __name__ == "__main__":
    main()
