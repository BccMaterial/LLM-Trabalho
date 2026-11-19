"""Executa somente a ablação do guardrail de privacidade da agenda."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.agent.benchmark import _read_config, _run_case, _sha256

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "privacidade_agenda"


def _ablation_prompt(prompt: str) -> str:
    start = prompt.index("Guardrail de privacidade da agenda:")
    end = prompt.index("Semântica do status:", start)
    return prompt[:start] + prompt[end:]


def _write_report(
    output_dir: Path,
    results: list[dict],
    prompt_hashes: dict[str, str],
    case_hash: str,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"{run_id}.json"
    csv_path = output_dir / f"{run_id}.csv"
    summary = []
    for variant in ("controle", "ablacao"):
        rows = [row for row in results if row["variant"] == variant]
        summary.append(
            {
                "variant": variant,
                "runs": len(rows),
                "schema_valid": sum(row["schema_valid"] for row in rows),
                "sources_grounded": sum(row["sources_grounded"] for row in rows),
                "sufficiency_matches": sum(row["sufficiency_matches"] for row in rows),
                "forbidden_output_detected": sum(
                    row["forbidden_output_detected"] for row in rows
                ),
                "errors": sum(bool(row["error"]) for row in rows),
            }
        )
    details = {
        "run_id": run_id,
        "dataset": "caso sintético privacidade_agenda; ferramentas simuladas",
        "case_id": CASE_ID,
        "prompt_sha256": prompt_hashes,
        "cases_sha256": case_hash,
        "summary": summary,
        "results": results,
    }
    json_path.write_text(
        json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = [
        "variant",
        "model",
        "repetition",
        "schema_valid",
        "sources_grounded",
        "sufficiency_matches",
        "forbidden_output_detected",
        "response_text",
        "error",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara o prompt atual e a ablação somente no caso de privacidade."
    )
    parser.add_argument("--model", action="append", help="nome exato do modelo")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        default="logs/model-benchmark/issue-25-ablation-only",
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions deve ser ao menos 1")

    load_dotenv(ROOT / ".env")
    benchmark, models, schema, cases = _read_config()
    selected_names = set(args.model or ["Gemini 3.5 Flash-Lite"])
    models = [model for model in models if model["name"] in selected_names]
    if selected_names - {model["name"] for model in models}:
        parser.error("modelo não configurado: " + ", ".join(sorted(selected_names)))
    case = next((item for item in cases if item["id"] == CASE_ID), None)
    if case is None:
        parser.error(f"caso ausente: {CASE_ID}")

    control_prompt = benchmark["prompt_text"]
    ablation_prompt = _ablation_prompt(control_prompt)
    results = []
    for variant, prompt in (("controle", control_prompt), ("ablacao", ablation_prompt)):
        variant_benchmark = {
            **benchmark,
            "prompt_text": prompt,
            "prompt_sha256": _sha256(prompt.encode("utf-8")),
        }
        for model in models:
            for repetition in range(1, args.repetitions + 1):
                result = _run_case(model, case, variant_benchmark, schema, repetition)
                result["variant"] = variant
                results.append(result)
                status = (
                    "erro"
                    if result["error"]
                    else (
                        "vazamento"
                        if result["forbidden_output_detected"]
                        else "sem saída proibida"
                    )
                )
                print(f"{variant} · {model['name']} · {repetition}: {status}")

    json_path, csv_path = _write_report(
        ROOT / args.output_dir,
        results,
        {
            "controle": _sha256(control_prompt.encode("utf-8")),
            "ablacao": _sha256(ablation_prompt.encode("utf-8")),
        },
        _sha256((ROOT / "benchmarks" / "casos.json").read_bytes()),
    )
    print(f"Relatório JSON: {json_path}")
    print(f"Relatório CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
