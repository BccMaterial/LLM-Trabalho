import json
from urllib.parse import parse_qs, urlsplit

from src.judge import observability_metrics
from src.judge.observability_metrics import analyze


def _tag(key, value):
    return {
        "key": key,
        "type": "string" if isinstance(value, str) else "json",
        "value": value,
    }


def _execution(index, passed=True, dirty=False, include_trace=True):
    run_id = f"run-{index}"
    case_id = f"case-{index}"
    commit = "a" * 40
    version = "issue-61"
    run = {
        "run_id": run_id,
        "version": version,
        "commit": commit,
        "agent_version": "0.1.0",
        "dataset_sha256": "b" * 64,
        "judge_prompt_sha256": "c" * 64,
        "judge_validation_sha256": "d" * 64,
        "created_at": f"2026-01-01T00:00:{index:02d}+00:00",
        "working_tree_dirty": dirty,
        "status": "concluida",
        "judge_enabled": True,
        "judge_validation_decision": "juiz_adotado",
        "agent_model": "openai/gpt-oss-20b",
        "results": [
            {
                "case_id": case_id,
                "passed": passed,
                "inconclusivo": False,
                "trace_correlation": {
                    "run_id": run_id,
                    "case_id": case_id,
                    "version": version,
                    "commit": commit,
                },
            }
        ],
    }
    if not include_trace:
        return run, None

    tags = [
        _tag("app.evaluation.run_id", run_id),
        _tag("app.evaluation.case_id", case_id),
        _tag("app.evaluation.version", version),
        _tag("app.evaluation.commit", commit),
        _tag("app.system.version", "0.1.0"),
        _tag("app.termination.reason", "completed"),
        _tag("app.output.status", "informacao_encontrada"),
        _tag("app.output.sufficiency", "suficiente"),
        _tag("app.output.source_types", json.dumps(["api"])),
    ]
    trace = {
        "traceID": f"{index:032x}",
        "processes": {"p1": {"serviceName": "llm-trabalho-agent"}},
        "spans": [
            {
                "spanID": "root",
                "operationName": "invoke_agent",
                "startTime": index * 1000,
                "duration": index * 1000,
                "processID": "p1",
                "tags": tags,
            },
            {
                "spanID": "chat",
                "operationName": "chat",
                "startTime": index * 1000,
                "duration": 500,
                "processID": "p1",
                "tags": [
                    _tag("gen_ai.usage.input_tokens", 1000),
                    _tag("gen_ai.usage.output_tokens", 100),
                ],
            },
            {
                "spanID": "tool",
                "operationName": "execute_tool",
                "startTime": index * 1000,
                "duration": 100,
                "processID": "p1",
                "tags": [
                    _tag("gen_ai.tool.name", "consultar_disponibilidade"),
                    _tag(
                        "app.tool.result.status",
                        "error" if index <= 2 else "success",
                    ),
                ],
            },
        ],
    }
    return run, trace


def test_analyze_measures_sli_metrics_cost_and_error_budget_for_30_runs():
    evidence = [_execution(index, passed=index > 3) for index in range(1, 31)]

    report = analyze(
        [run for run, _ in evidence],
        [trace for _, trace in evidence],
        pricing_tier="paid",
    )

    version = report["versions"]["issue-61"]
    assert version["valid_executions"] == 30
    assert version["quality_sli"]["observed_rate"] == 0.9
    assert version["quality_sli"]["measured_value"] == 0.9
    assert version["quality_sli"]["status"] == "met"
    assert version["quality_sli"]["error_budget"] == {
        "allowed_failed_executions": 3,
        "consumed_failed_executions": 3,
        "consumption": 1.0,
    }
    assert version["operations"]["latency_ms"]["p50"] == 15.0
    assert version["operations"]["latency_ms"]["p95"] == 29.0
    assert version["executions"][0]["root_span_count"] == 1
    assert version["business"]["output_source_type_distribution"] == {"api": 30}
    assert version["operations"]["tool_error_rates"]["consultar_disponibilidade"] == {
        "calls": 30,
        "errors": 2,
        "error_rate": 0.0667,
    }
    assert version["payer"]["priced_executions"] == 30
    assert version["payer"]["average_per_execution"] == 0.000105
    assert version["executions"][0]["estimated_cost"]["value"] == 0.000105
    assert version["system_owner"]["trace_coverage"] == 1.0
    assert version["system_owner"]["agent_versions"] == ["0.1.0"]


def test_analyze_does_not_measure_a_dirty_run_or_missing_trace():
    dirty_run, dirty_trace = _execution(1, dirty=True)
    missing_trace_run, _ = _execution(2, include_trace=False)

    report = analyze(
        [dirty_run, missing_trace_run],
        [dirty_trace],
        pricing_tier="paid",
    )

    version = report["versions"]["issue-61"]
    assert version["valid_executions"] == 0
    assert version["quality_sli"]["measured_value"] is None
    assert version["quality_sli"]["status"] == "insufficient_sample"
    assert version["excluded_executions"] == 2
    assert report["excluded_reason_counts"]["worktree_sujo_ou_desconhecido"] == 1
    assert report["excluded_reason_counts"]["trace_raiz_ausente"] == 1


def test_fetch_jaeger_traces_queries_the_agent_root_operation(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"data": [{"traceID": "trace"}]}).encode()

    def fake_urlopen(url, timeout):
        assert timeout == 30
        query = parse_qs(urlsplit(url).query)
        assert query == {
            "service": ["llm-trabalho-agent"],
            "operation": ["invoke_agent"],
            "lookback": ["6h"],
            "limit": ["42"],
        }
        return Response()

    monkeypatch.setattr(observability_metrics, "urlopen", fake_urlopen)

    assert observability_metrics.fetch_jaeger_traces(
        "http://localhost:16686/",
        lookback="6h",
        limit=42,
    ) == [{"traceID": "trace"}]


def test_analyze_keeps_different_commits_out_of_one_version_cohort():
    first_run, first_trace = _execution(1)
    second_run, second_trace = _execution(2)
    second_run["commit"] = "b" * 40

    report = analyze(
        [first_run, second_run],
        [first_trace, second_trace],
        pricing_tier="paid",
    )

    version = report["versions"]["issue-61"]
    assert version["valid_executions"] == 0
    assert version["excluded_executions"] == 2
    assert report["excluded_reason_counts"]["coorte_inconsistente"] == 2
