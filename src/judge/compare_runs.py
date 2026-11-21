"""Compara duas rodadas versionadas da suíte e reporta métricas e deltas."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.judge.rubric import ROOT, read_json


def _load(path: Path) -> tuple[dict[str, Any], list[dict], dict[str, Any]]:
    run = read_json(path / "run.json")
    results = read_json(path / "results.json")
    summary = read_json(path / "summary.json")
    return run, results["cases"], summary


def rate(records: list[dict]) -> dict[str, Any]:
    conclusive = [record for record in records if not record.get("inconclusivo")]
    total = len(conclusive)
    passed = sum(int(record["passed"]) for record in conclusive)
    return {
        "total": total,
        "passed": passed,
        "rate": passed / total if total else 0.0,
        "inconclusivos": len(records) - total,
    }


def _delta(after: float, before: float) -> float:
    return round(after - before, 4)


def build_report(before_dir: Path, after_dir: Path) -> dict[str, Any]:
    before_run, before_cases, before_summary = _load(before_dir)
    after_run, after_cases, after_summary = _load(after_dir)
    if before_run["dataset_sha256"] != after_run["dataset_sha256"]:
        raise ValueError("as rodadas usaram datasets diferentes; não são comparáveis")

    before_by_id = {case["case_id"]: case for case in before_cases}
    after_by_id = {case["case_id"]: case for case in after_cases}
    if set(before_by_id) != set(after_by_id):
        raise ValueError("as rodadas não cobrem exatamente os mesmos casos")

    classes = sorted({case["classe"] for case in after_cases})
    by_class = []
    for name in classes:
        before_stats = rate([case for case in before_cases if case["classe"] == name])
        after_stats = rate([case for case in after_cases if case["classe"] == name])
        by_class.append(
            {
                "classe": name,
                "antes": before_stats,
                "depois": after_stats,
                "delta": _delta(after_stats["rate"], before_stats["rate"]),
            }
        )

    before_rate = rate(before_cases)
    after_rate = rate(after_cases)
    warnings = []
    if before_run["agent_prompt_sha256"] != after_run["agent_prompt_sha256"]:
        warnings.append("o prompt do agente mudou entre as rodadas")
    if before_run["judge"]["model"] != after_run["judge"]["model"]:
        warnings.append("o modelo do juiz mudou entre as rodadas")
    if before_run.get("judge_enabled") != after_run.get("judge_enabled"):
        warnings.append("o juiz esteve ativo em apenas uma das rodadas")

    regressions = []
    improvements = []
    inconclusive_before = sorted(
        case["case_id"] for case in before_cases if case.get("inconclusivo")
    )
    inconclusive_after = sorted(
        case["case_id"] for case in after_cases if case.get("inconclusivo")
    )
    inconclusive = inconclusive_after
    for case_id in sorted(after_by_id):
        if before_by_id[case_id].get("inconclusivo") or after_by_id[case_id].get(
            "inconclusivo"
        ):
            continue
        was = before_by_id[case_id]["passed"]
        now = after_by_id[case_id]["passed"]
        if was and not now:
            regressions.append(
                {
                    "case_id": case_id,
                    "classe": after_by_id[case_id]["classe"],
                    "failed_checks": after_by_id[case_id]["failed_checks"],
                }
            )
        elif not was and now:
            improvements.append(
                {
                    "case_id": case_id,
                    "classe": after_by_id[case_id]["classe"],
                    "antes_falhou": before_by_id[case_id]["failed_checks"],
                }
            )

    return {
        "before": {
            "run_id": before_run["run_id"],
            "version": before_run["version"],
            "commit": before_run["commit"],
            "change": before_run["change"],
            "dataset_sha256": before_run["dataset_sha256"],
            "judge": before_run["judge"]["model"],
            "summary": before_summary,
        },
        "after": {
            "run_id": after_run["run_id"],
            "version": after_run["version"],
            "commit": after_run["commit"],
            "change": after_run["change"],
            "dataset_sha256": after_run["dataset_sha256"],
            "judge": after_run["judge"]["model"],
            "summary": after_summary,
        },
        "media": {
            "antes": round(before_rate["rate"], 4),
            "depois": round(after_rate["rate"], 4),
            "delta": _delta(after_rate["rate"], before_rate["rate"]),
        },
        "media_por_classe": {
            "antes": before_summary["media_por_classe"],
            "depois": after_summary["media_por_classe"],
            "delta": _delta(
                after_summary["media_por_classe"], before_summary["media_por_classe"]
            ),
        },
        "por_classe": by_class,
        "regressoes": regressions,
        "melhorias": improvements,
        "inconclusivos": inconclusive,
        "inconclusivos_antes": inconclusive_before,
        "inconclusivos_depois": inconclusive_after,
        "avisos": warnings,
    }


def format_markdown(report: dict[str, Any]) -> str:
    before, after = report["before"], report["after"]
    lines = [
        "# Comparação de rodadas da suíte",
        "",
        f"Antes: **{before['version']}** ({before['run_id']}, commit "
        f"`{before['commit'][:12]}`).",
        f"Depois: **{after['version']}** ({after['run_id']}, commit "
        f"`{after['commit'][:12]}`).",
        "",
        f"Dataset: `{before['dataset_sha256'][:16]}…` (igual nas duas rodadas).",
        f"Juiz: `{before['judge']}` → `{after['judge']}`.",
        "",
        f"Mudança avaliada: {after['change']}",
        "",
        "| Classe | Antes | Depois | Delta |",
        "|---|---:|---:|---:|",
    ]
    for item in report["por_classe"]:
        lines.append(
            f"| {item['classe']} | {item['antes']['passed']}/{item['antes']['total']} "
            f"({item['antes']['rate']:.0%}) | "
            f"{item['depois']['passed']}/{item['depois']['total']} "
            f"({item['depois']['rate']:.0%}) | {item['delta']:+.0%} |"
        )
    lines += [
        "",
        f"Média geral: {report['media']['antes']:.0%} → "
        f"{report['media']['depois']:.0%} "
        f"({report['media']['delta']:+.0%}).",
        f"Média por classe: {report['media_por_classe']['antes']:.0%} → "
        f"{report['media_por_classe']['depois']:.0%} "
        f"({report['media_por_classe']['delta']:+.0%}).",
        "",
    ]
    inconclusive_before = report["inconclusivos_antes"]
    inconclusive_after = report["inconclusivos_depois"]
    if inconclusive_before or inconclusive_after:
        before_text = (
            ", ".join(f"`{case_id}`" for case_id in inconclusive_before) or "nenhum"
        )
        after_text = (
            ", ".join(f"`{case_id}`" for case_id in inconclusive_after) or "nenhum"
        )
        lines.append(
            f"Casos inconclusivos (fora do denominador): antes: {before_text}; "
            f"depois: {after_text}."
        )
        lines.append("")
    if report["melhorias"]:
        lines.append("Melhorias:")
        for item in report["melhorias"]:
            lines.append(f"- `{item['case_id']}` ({item['classe']})")
        lines.append("")
    if report["regressoes"]:
        lines.append("Regressões:")
        for item in report["regressoes"]:
            lines.append(
                f"- `{item['case_id']}` ({item['classe']}): "
                f"{', '.join(item['failed_checks'])}"
            )
        lines.append("")
    else:
        lines.append("Sem regressões: nenhum caso aprovado antes falhou depois.")
        lines.append("")
    if report["avisos"]:
        lines.append("Avisos de comparabilidade:")
        for warning in report["avisos"]:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="arquivo Markdown de saída")
    args = parser.parse_args()
    before = args.before if args.before.is_absolute() else ROOT / args.before
    after = args.after if args.after.is_absolute() else ROOT / args.after
    report = build_report(before, after)
    markdown = format_markdown(report)
    print(markdown)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
