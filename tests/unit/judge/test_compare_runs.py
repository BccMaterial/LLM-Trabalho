from src.judge.compare_runs import build_report, format_markdown
from src.judge.rubric import write_json


def _run(path, *, version, commit, change, records):
    path.mkdir(parents=True, exist_ok=True)
    write_json(
        path / "run.json",
        {
            "run_id": path.name,
            "version": version,
            "commit": commit,
            "change": change,
            "dataset_sha256": "dataset-hash",
            "agent_prompt_sha256": "prompt-hash",
            "judge": {"model": "juiz-v1"},
            "judge_enabled": True,
        },
    )
    write_json(path / "results.json", {"cases": records})
    passed = sum(record["passed"] for record in records)
    write_json(
        path / "summary.json",
        {
            "media": passed / len(records),
            "media_por_classe": passed / len(records),
        },
    )


def _record(case_id, classe, passed, failed=None):
    return {
        "case_id": case_id,
        "classe": classe,
        "passed": passed,
        "failed_checks": failed or [],
    }


def test_comparison_shows_per_class_rates_mean_delta_and_regressions(tmp_path):
    before = tmp_path / "antes"
    after = tmp_path / "depois"
    _run(
        before,
        version="v1",
        commit="aaaaaaaaaaaa",
        change="baseline",
        records=[
            _record("a", "classe-a", True),
            _record("b", "classe-b", True),
            _record("c", "classe-b", False, ["efeito_estado"]),
        ],
    )
    _run(
        after,
        version="v2",
        commit="bbbbbbbbbbbb",
        change="mudança real",
        records=[
            _record("a", "classe-a", True),
            _record("b", "classe-b", False, ["juiz_clareza"]),
            _record("c", "classe-b", True),
        ],
    )

    report = build_report(before, after)
    assert report["media"]["delta"] == 0.0
    assert [item["classe"] for item in report["por_classe"]] == ["classe-a", "classe-b"]
    assert report["por_classe"][1]["delta"] == 0.0
    assert [item["case_id"] for item in report["regressoes"]] == ["b"]
    assert [item["case_id"] for item in report["melhorias"]] == ["c"]
    assert report["avisos"] == []

    markdown = format_markdown(report)
    assert "| classe-b |" in markdown
    assert "Regressões:" in markdown
    assert "`b`" in markdown
    assert "mudança real" in markdown


def test_comparison_rejects_different_datasets(tmp_path):
    before = tmp_path / "antes"
    after = tmp_path / "depois"
    _run(
        before,
        version="v1",
        commit="a" * 12,
        change="baseline",
        records=[_record("a", "classe-a", True)],
    )
    _run(
        after,
        version="v2",
        commit="b" * 12,
        change="nova",
        records=[_record("a", "classe-a", True)],
    )
    data = __import__("json").loads((after / "run.json").read_text())
    data["dataset_sha256"] = "outro-hash"
    write_json(after / "run.json", data)

    try:
        build_report(before, after)
    except ValueError as error:
        assert "datasets diferentes" in str(error)
    else:
        raise AssertionError("comparação deveria rejeitar datasets diferentes")
