"""Mede métricas por versão a partir de resultados versionados e traces Jaeger."""

from __future__ import annotations

import argparse
import json
import math
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from src.agent.observability import SERVICE_NAME_VALUE

ROOT = Path(__file__).resolve().parents[2]
MIN_VALID_EXECUTIONS = 30
SLO_TARGET = 0.90
ROOT_OPERATION = "invoke_agent"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path} deve conter um objeto JSON.")
    return value


def load_run_evidence(run_dirs: list[Path]) -> list[dict[str, Any]]:
    evidence = []
    for run_dir in run_dirs:
        run = _read_json(run_dir / "run.json")
        results = _read_json(run_dir / "results.json")
        if not isinstance(results.get("cases"), list):
            raise ValueError(f"{run_dir / 'results.json'} não contém a lista cases.")
        run["results"] = results["cases"]
        run["evidence_path"] = str(run_dir)
        evidence.append(run)
    return evidence


def fetch_jaeger_traces(
    jaeger_url: str,
    *,
    lookback: str = "24h",
    limit: int = 1000,
) -> list[dict[str, Any]]:
    query = urlencode(
        {
            "service": SERVICE_NAME_VALUE,
            "operation": ROOT_OPERATION,
            "lookback": lookback,
            "limit": limit,
        }
    )
    url = f"{jaeger_url.rstrip('/')}/api/traces?{query}"
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("A API Jaeger retornou uma resposta JSON inválida.")
    traces = payload.get("data")
    if not isinstance(traces, list):
        raise ValueError("A API Jaeger não retornou uma lista data de traces.")
    return traces


def _span_tags(span: dict[str, Any]) -> dict[str, Any]:
    tags = {}
    for item in span.get("tags", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if value is None:
            for candidate in (
                "stringValue",
                "boolValue",
                "intValue",
                "floatValue",
                "jsonValue",
            ):
                if candidate in item:
                    value = item[candidate]
                    break
        tags[item["key"]] = value
    return tags


def _integer(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return round(ordered[rank - 1], 3)


def _model_prices(model_id: str, tier: str) -> dict[str, Any] | None:
    if tier not in {"listed", "paid"}:
        raise ValueError(f"Faixa tarifária inválida: {tier}")
    with (ROOT / "benchmarks" / "modelos.toml").open("rb") as file:
        models = tomllib.load(file).get("models", [])
    model = next((item for item in models if item.get("model_id") == model_id), None)
    if model is None:
        return None
    if tier == "paid":
        input_price = model.get(
            "paid_input_price_per_million", model.get("input_price_per_million")
        )
        output_price = model.get(
            "paid_output_price_per_million", model.get("output_price_per_million")
        )
    else:
        input_price = model.get("input_price_per_million")
        output_price = model.get("output_price_per_million")
    if not isinstance(input_price, (int, float)) or not isinstance(
        output_price, (int, float)
    ):
        return None
    return {
        "currency": model.get("currency", "unknown"),
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
        "price_checked": model.get("price_checked"),
        "pricing_source": model.get("pricing_source"),
    }


def _trace_execution_groups(
    traces: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "roots": [],
            "chats": [],
            "tools": [],
            "trace_ids": set(),
            "metadata_errors": set(),
        }
    )
    for trace in traces:
        trace_id = trace.get("traceID")
        spans = [span for span in trace.get("spans", []) if isinstance(span, dict)]
        roots = [
            span
            for span in spans
            if span.get("operationName") == ROOT_OPERATION
            and trace.get("processes", {})
            .get(span.get("processID"), {})
            .get("serviceName")
            == SERVICE_NAME_VALUE
        ]
        for root in roots:
            tags = _span_tags(root)
            run_id = tags.get("app.evaluation.run_id")
            case_id = tags.get("app.evaluation.case_id")
            version = tags.get("app.evaluation.version")
            commit = tags.get("app.evaluation.commit")
            system_version = tags.get("app.system.version")
            if not all(isinstance(value, str) and value for value in (run_id, case_id)):
                continue
            group = groups[(run_id, case_id)]
            group["roots"].append({"span": root, "tags": tags})
            if isinstance(trace_id, str):
                group["trace_ids"].add(trace_id)
            group["metadata_errors"].add((version, commit, system_version))
            for span in spans:
                span_tags = _span_tags(span)
                if span.get("operationName") == "chat":
                    group["chats"].append({"span": span, "tags": span_tags})
                elif span.get("operationName") == "execute_tool":
                    group["tools"].append({"span": span, "tags": span_tags})
    return groups


def _execution_metrics(group: dict[str, Any]) -> dict[str, Any]:
    roots = sorted(
        group["roots"],
        key=lambda item: item["span"].get("startTime", 0),
    )
    durations = [
        span["duration"]
        for item in roots
        if isinstance((span := item["span"]).get("duration"), (int, float))
        and span["duration"] >= 0
    ]
    latest_tags = roots[-1]["tags"] if roots else {}
    termination_reason = next(
        (
            item["tags"].get("app.termination.reason")
            for item in reversed(roots)
            if isinstance(item["tags"].get("app.termination.reason"), str)
        ),
        "not_recorded",
    )
    input_counts = [
        _integer(item["tags"].get("gen_ai.usage.input_tokens"))
        for item in group["chats"]
    ]
    output_counts = [
        _integer(item["tags"].get("gen_ai.usage.output_tokens"))
        for item in group["chats"]
    ]
    usage_complete = bool(group["chats"]) and all(
        value is not None for value in [*input_counts, *output_counts]
    )
    tool_counts: Counter[str] = Counter()
    tool_errors: Counter[str] = Counter()
    for item in group["tools"]:
        name = item["tags"].get("gen_ai.tool.name", "unknown")
        name = name if isinstance(name, str) else "unknown"
        tool_counts[name] += 1
        if (
            item["tags"].get("app.tool.result.status") == "error"
            or item["tags"].get("otel.status_code") == "ERROR"
            or item["tags"].get("error") is True
            or isinstance(item["tags"].get("error.type"), str)
        ):
            tool_errors[name] += 1
    source_types = latest_tags.get("app.output.source_types", [])
    if isinstance(source_types, str):
        try:
            decoded_source_types = json.loads(source_types)
        except json.JSONDecodeError:
            decoded_source_types = source_types
        source_types = (
            decoded_source_types
            if isinstance(decoded_source_types, list)
            else [decoded_source_types]
        )
    if not isinstance(source_types, list):
        source_types = []
    return {
        "trace_ids": sorted(group["trace_ids"]),
        "root_count": len(roots),
        "latency_ms": round(sum(durations) / 1000, 3) if durations else None,
        "termination_reason": termination_reason,
        "output_status": latest_tags.get("app.output.status"),
        "output_sufficiency": latest_tags.get("app.output.sufficiency"),
        "output_source_types": source_types,
        "input_tokens": (
            sum(value for value in input_counts if value is not None)
            if input_counts
            else None
        ),
        "output_tokens": (
            sum(value for value in output_counts if value is not None)
            if output_counts
            else None
        ),
        "usage_complete": usage_complete,
        "tool_calls": dict(tool_counts),
        "tool_errors": dict(tool_errors),
    }


def _rate_distribution(
    calls: Counter[str], errors: Counter[str]
) -> dict[str, dict[str, float | int]]:
    return {
        name: {
            "calls": count,
            "errors": errors[name],
            "error_rate": round(errors[name] / count, 4) if count else 0.0,
        }
        for name, count in sorted(calls.items())
    }


def analyze(
    runs: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    *,
    pricing_tier: str,
) -> dict[str, Any]:
    if pricing_tier not in {"listed", "paid"}:
        raise ValueError(f"Faixa tarifária inválida: {pricing_tier}")
    groups = _trace_execution_groups(traces)
    versions: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": [], "executions": []}
    )
    excluded = Counter()
    seen: set[tuple[str, str]] = set()
    cohort_signatures: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
    signature_fields = (
        "commit",
        "agent_version",
        "dataset_sha256",
        "agent_model",
        "judge_prompt_sha256",
        "judge_validation_sha256",
    )
    for run in runs:
        version = run.get("version")
        if isinstance(version, str):
            cohort_signatures[version].add(
                tuple(run.get(field) for field in signature_fields)
            )

    for run in runs:
        run_id = run.get("run_id")
        version = run.get("version")
        if not isinstance(run_id, str) or not isinstance(version, str):
            excluded["identidade_de_execucao_ausente"] += len(run.get("results", []))
            continue
        version_data = versions[version]
        version_data["runs"].append(
            {
                "run_id": run_id,
                "commit": run.get("commit"),
                "agent_version": run.get("agent_version"),
                "agent_model": run.get("agent_model"),
                "created_at": run.get("created_at"),
                "working_tree_dirty": run.get("working_tree_dirty"),
                "dataset_sha256": run.get("dataset_sha256"),
            }
        )
        for record in run.get("results", []):
            case_id = record.get("case_id")
            key = (run_id, case_id) if isinstance(case_id, str) else None
            reasons = []
            if key is None:
                reasons.append("case_id_ausente")
            elif key in seen:
                reasons.append("caso_duplicado")
            else:
                seen.add(key)
            if run.get("working_tree_dirty") is not False:
                reasons.append("worktree_sujo_ou_desconhecido")
            if run.get("status") != "concluida":
                reasons.append("rodada_incompleta")
            if not isinstance(run.get("commit"), str) or run["commit"] in {
                "",
                "unknown",
            }:
                reasons.append("commit_ausente")
            if any(
                not isinstance(run.get(field), str) or not run[field]
                for field in signature_fields[1:]
            ):
                reasons.append("metadado_de_versao_ausente")
            if len(cohort_signatures[version]) > 1:
                reasons.append("coorte_inconsistente")
            if run.get("judge_enabled") is not True:
                reasons.append("juiz_desativado")
            if run.get("judge_validation_decision") != "juiz_adotado":
                reasons.append("juiz_nao_adotado")
            if record.get("inconclusivo") is True:
                reasons.append("avaliacao_inconclusiva")

            group = groups.get(key) if key else None
            execution = _execution_metrics(group) if group else None
            expected_correlation = {
                "run_id": run_id,
                "case_id": case_id,
                "version": version,
                "commit": run.get("commit"),
            }
            if record.get("trace_correlation") != expected_correlation:
                reasons.append("correlacao_ausente_ou_incompativel")
            if not group or not group["roots"] or not execution["trace_ids"]:
                reasons.append("trace_raiz_ausente")
            elif group["metadata_errors"] != {
                (version, run.get("commit"), run.get("agent_version"))
            }:
                reasons.append("metadados_do_trace_incompativeis")

            detail = {
                "run_id": run_id,
                "case_id": case_id,
                "version": version,
                "commit": run.get("commit"),
                "passed": record.get("passed") is True,
                "valid": not reasons,
                "exclusion_reasons": reasons,
                "trace_ids": execution["trace_ids"] if execution else [],
            }
            if execution:
                detail.update(
                    {
                        "root_span_count": execution["root_count"],
                        "latency_ms": execution["latency_ms"],
                        "termination_reason": execution["termination_reason"],
                        "output_status": execution["output_status"],
                        "output_sufficiency": execution["output_sufficiency"],
                        "output_source_types": execution["output_source_types"],
                        "input_tokens": execution["input_tokens"],
                        "output_tokens": execution["output_tokens"],
                        "usage_complete": execution["usage_complete"],
                        "tool_calls": execution["tool_calls"],
                        "tool_errors": execution["tool_errors"],
                    }
                )
            for reason in reasons:
                excluded[reason] += 1
            version_data["executions"].append(detail)

    report_versions = {}
    for version, data in sorted(versions.items()):
        valid = [item for item in data["executions"] if item["valid"]]
        good = sum(item["passed"] for item in valid)
        failed = len(valid) - good
        observed_rate = good / len(valid) if valid else None
        measured = len(valid) >= MIN_VALID_EXECUTIONS

        latency_values = [
            item["latency_ms"]
            for item in valid
            if isinstance(item.get("latency_ms"), (int, float))
        ]
        termination = Counter(item["termination_reason"] for item in valid)
        output_status = Counter(
            item["output_status"]
            for item in valid
            if isinstance(item.get("output_status"), str)
        )
        source_types = Counter(
            source
            for item in valid
            for source in item.get("output_source_types", [])
            if isinstance(source, str)
        )
        tool_calls: Counter[str] = Counter()
        tool_errors: Counter[str] = Counter()
        for item in valid:
            tool_calls.update(item.get("tool_calls", {}))
            tool_errors.update(item.get("tool_errors", {}))

        runs_by_id = {item["run_id"]: item for item in data["runs"]}
        priced_runs = {}
        for run_id, run in runs_by_id.items():
            model_id = run.get("agent_model")
            if isinstance(model_id, str):
                price = _model_prices(model_id, pricing_tier)
                if price is not None:
                    priced_runs[run_id] = (model_id, price)

        cost_records = []
        currencies = set()
        for item in valid:
            price_entry = priced_runs.get(item["run_id"])
            if not item.get("usage_complete") or not price_entry:
                continue
            model_id, price = price_entry
            currency = price["currency"]
            currencies.add(currency)
            cost = (
                item["input_tokens"] * price["input_price_per_million"]
                + item["output_tokens"] * price["output_price_per_million"]
            ) / 1_000_000
            cost_records.append(
                {
                    "run_id": item["run_id"],
                    "case_id": item["case_id"],
                    "model_id": model_id,
                    "currency": currency,
                    "cost": cost,
                    "pricing_source": price["pricing_source"],
                    "price_checked": price["price_checked"],
                }
            )
        cost_by_execution = {
            (item["run_id"], item["case_id"]): item for item in cost_records
        }
        for item in data["executions"]:
            cost_record = cost_by_execution.get((item["run_id"], item["case_id"]))
            item["estimated_cost"] = (
                {
                    "value": round(cost_record["cost"], 10),
                    "currency": cost_record["currency"],
                    "model_id": cost_record["model_id"],
                    "pricing_source": cost_record["pricing_source"],
                    "price_checked": cost_record["price_checked"],
                }
                if cost_record
                else None
            )
        cost_is_comparable = len(currencies) <= 1
        cost_complete = len(cost_records) == len(valid) and bool(valid)
        token_records = [item for item in valid if item.get("usage_complete")]
        cost_summary = {
            "tier": pricing_tier,
            "currency": next(iter(currencies)) if len(currencies) == 1 else None,
            "priced_executions": len(cost_records),
            "valid_executions": len(valid),
            "coverage": round(len(cost_records) / len(valid), 4) if valid else 0.0,
            "token_usage_executions": len(token_records),
            "input_tokens_total": sum(item["input_tokens"] for item in token_records),
            "output_tokens_total": sum(item["output_tokens"] for item in token_records),
            "average_input_tokens": (
                round(
                    sum(item["input_tokens"] for item in token_records)
                    / len(token_records)
                )
                if token_records
                else None
            ),
            "average_output_tokens": (
                round(
                    sum(item["output_tokens"] for item in token_records)
                    / len(token_records)
                )
                if token_records
                else None
            ),
            "average_per_execution": (
                round(sum(item["cost"] for item in cost_records) / len(valid), 10)
                if cost_complete and cost_is_comparable
                else None
            ),
            "total": (
                round(sum(item["cost"] for item in cost_records), 10)
                if cost_complete and cost_is_comparable
                else None
            ),
            "pricing_sources": sorted(
                {
                    item["pricing_source"]
                    for item in cost_records
                    if isinstance(item["pricing_source"], str)
                }
            ),
            "price_checked": sorted(
                {
                    item["price_checked"]
                    for item in cost_records
                    if isinstance(item["price_checked"], str)
                }
            ),
            "note": (
                "Estimativa por tokens e tarifa declarada; não é uma fatura."
                if cost_records
                else "Custo indisponível: tokens completos ou tarifa do modelo ausentes."
            ),
        }
        allowed_failures = math.floor((1 - SLO_TARGET) * len(valid) + 1e-12)
        report_versions[version] = {
            "runs": data["runs"],
            "valid_executions": len(valid),
            "excluded_executions": len(data["executions"]) - len(valid),
            "good_executions": good,
            "failed_executions": failed,
            "quality_sli": {
                "definition": (
                    "casos aprovados / casos conclusivos com juiz adotado, "
                    "worktree limpo e trace correlacionado à versão/commit"
                ),
                "target": SLO_TARGET,
                "observed_rate": (
                    round(observed_rate, 4) if observed_rate is not None else None
                ),
                "measured_value": (
                    round(observed_rate, 4)
                    if measured and observed_rate is not None
                    else None
                ),
                "minimum_sample": MIN_VALID_EXECUTIONS,
                "status": (
                    "met"
                    if measured
                    and observed_rate is not None
                    and observed_rate >= SLO_TARGET
                    else "missed" if measured else "insufficient_sample"
                ),
                "error_budget": {
                    "allowed_failed_executions": allowed_failures,
                    "consumed_failed_executions": failed,
                    "consumption": (
                        round(failed / allowed_failures, 4)
                        if allowed_failures
                        else None
                    ),
                },
            },
            "business": {
                "output_status_distribution": dict(sorted(output_status.items())),
                "output_source_type_distribution": dict(sorted(source_types.items())),
            },
            "operations": {
                "latency_ms": {
                    "sample_count": len(latency_values),
                    "p50": _percentile(latency_values, 0.50),
                    "p95": _percentile(latency_values, 0.95),
                    "scope": "soma das durações dos spans invoke_agent por caso",
                },
                "termination_reasons": dict(sorted(termination.items())),
                "tool_error_rates": _rate_distribution(tool_calls, tool_errors),
            },
            "payer": cost_summary,
            "system_owner": {
                "agent_versions": sorted(
                    {
                        run.get("agent_version")
                        for run in data["runs"]
                        if isinstance(run.get("agent_version"), str)
                    }
                ),
                "commit_count": len(
                    {run.get("commit") for run in data["runs"] if run.get("commit")}
                ),
                "trace_coverage": (
                    round(
                        sum(bool(item.get("trace_ids")) for item in data["executions"])
                        / len(data["executions"]),
                        4,
                    )
                    if data["executions"]
                    else 0.0
                ),
                "trace_ids": {
                    f"{item['run_id']}:{item['case_id']}": item.get("trace_ids", [])
                    for item in data["executions"]
                    if item.get("trace_ids")
                },
            },
            "executions": data["executions"],
        }

    return {
        "slo_window": (
            "coorte de todas as execuções sintéticas válidas fornecidas por versão; "
            f"mínimo de {MIN_VALID_EXECUTIONS} válidas"
        ),
        "pricing_tier": pricing_tier,
        "versions": report_versions,
        "excluded_reason_counts": dict(sorted(excluded.items())),
        "trace_count": len(traces),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Medição de observabilidade",
        "",
        f"Janela: {report['slo_window']}. Faixa tarifária: {report['pricing_tier']}.",
        "",
    ]
    if not report["versions"]:
        lines.extend(["Nenhuma execução versionada foi fornecida.", ""])
    for version, data in report["versions"].items():
        sli = data["quality_sli"]
        lines.extend(
            [
                f"## Versão {version}",
                "",
                f"- SLI: {sli['measured_value'] if sli['measured_value'] is not None else 'não medido'} "
                f"(observado: {sli['observed_rate']}, alvo: {sli['target']:.0%}; "
                f"status: {sli['status']}).",
                f"- Execuções válidas: {data['valid_executions']}; "
                f"excluídas: {data['excluded_executions']}.",
                f"- Orçamento de erro: {sli['error_budget']['consumed_failed_executions']}/"
                f"{sli['error_budget']['allowed_failed_executions']} falhas permitidas.",
                f"- Latência p50/p95: {data['operations']['latency_ms']['p50']}/"
                f"{data['operations']['latency_ms']['p95']} ms.",
                f"- Custo médio estimado por execução: "
                f"{data['payer']['average_per_execution']} "
                f"{data['payer']['currency'] or ''} "
                f"(cobertura {data['payer']['coverage']:.0%}).",
                f"- Motivos de término: {data['operations']['termination_reasons']}.",
                f"- Erros por ferramenta: {data['operations']['tool_error_rates']}.",
                "",
            ]
        )
    if report["excluded_reason_counts"]:
        lines.extend(
            [
                "## Lacunas de evidência",
                "",
                *[
                    f"- {reason}: {count}"
                    for reason, count in report["excluded_reason_counts"].items()
                ],
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        action="append",
        type=Path,
        required=True,
        help="diretório de uma rodada do run_suite.py; pode ser repetido",
    )
    parser.add_argument(
        "--jaeger-url",
        default="http://localhost:16686",
        help="URL base da API Jaeger",
    )
    parser.add_argument(
        "--lookback",
        default="24h",
        help="janela pesquisada no Jaeger, por exemplo 24h",
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--pricing-tier",
        choices=("listed", "paid"),
        default="paid",
        help="faixa usada na estimativa; não representa necessariamente a fatura",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/observability/measurement.json"),
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit deve ser positivo.")

    runs = load_run_evidence(args.run_dir)
    traces = fetch_jaeger_traces(
        args.jaeger_url,
        lookback=args.lookback,
        limit=args.limit,
    )
    report = analyze(runs, traces, pricing_tier=args.pricing_tier)
    report["trace_query"] = {
        "service": SERVICE_NAME_VALUE,
        "operation": ROOT_OPERATION,
        "lookback": args.lookback,
        "limit": args.limit,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Medição JSON: {args.output}")
    print(f"Resumo Markdown: {markdown_path}")
    for version, data in report["versions"].items():
        sli = data["quality_sli"]
        value = (
            f"{sli['measured_value']:.1%}"
            if sli["measured_value"] is not None
            else "não medido (amostra insuficiente)"
        )
        print(
            f"{version}: {value}; {data['valid_executions']} execuções válidas; "
            f"SLO {sli['status']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
