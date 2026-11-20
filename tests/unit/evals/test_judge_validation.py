import json
import re
from collections import Counter
from pathlib import Path

from scripts.validate_judge import (
    PROMPT_PATH,
    RUNS_DIR,
    VALIDATION_PATH,
    build_decision,
    build_prompt,
    compute_matrix,
    normalizar_decisao,
    verify_pre_registration,
)

ROOT = Path(__file__).parents[3]
VALIDATION = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
GOLDEN = json.loads((ROOT / "evals" / "golden_dataset.json").read_text("utf-8"))


def test_pre_registration_and_labelled_sample():
    verify_pre_registration(VALIDATION)
    cases = VALIDATION["cases"]
    labels = Counter(case["humano"]["decisao"] for case in cases)

    assert VALIDATION["pre_registration"]["threshold"] == 17
    assert VALIDATION["pre_registration"]["threshold_ratio"] == 0.85
    assert len(cases) == 20
    assert labels == {"SIM": 13, "NAO": 7}
    assert VALIDATION["labels"]["status"] == "revisado"
    assert VALIDATION["labels"]["reviewed_by"] == ["Thiago Pereira Lins da Silva"]
    assert VALIDATION["labels"]["reviewed_at"] == "2026-11-20"
    human_labels = {case["case_id"]: case["humano"]["decisao"] for case in cases}
    assert human_labels["dev-08-entrada-ambigua"] == "NAO"
    assert human_labels["syn-10-escolha-sem-especificacao"] == "SIM"
    assert {case["case_id"] for case in cases} == {
        case["id"] for case in GOLDEN["cases"]
    }
    assert VALIDATION["rubric"]["id"] == "clareza-utilidade-v1"
    assert all(
        case["humano"]["justificativa"] and case["humano"]["decisao"] in {"SIM", "NAO"}
        for case in cases
    )


def test_prompt_is_blind_and_uses_single_fixed_format():
    template = PROMPT_PATH.read_text(encoding="utf-8")
    assert "__PEDIDO__" in template
    assert "__CONTEXTO__" in template
    assert "__SAIDA__" in template
    assert "decisao" in template and "SIM" in template and "NAO" in template

    for case in VALIDATION["cases"]:
        prompt = build_prompt(case)
        assert case["pedido"] in prompt
        assert case["humano"]["justificativa"] not in prompt
        assert case["case_id"] not in prompt
        assert "origem" not in prompt
        assert "proveniencia" not in prompt
        assert '"esperado"' not in prompt
        assert '"classe"' not in prompt
        assert '"humano"' not in prompt


def test_matrix_and_decision_match_versioned_result():
    matrix = compute_matrix(VALIDATION)
    decision = build_decision(VALIDATION, matrix)

    assert matrix == VALIDATION["matrix"]
    assert decision == VALIDATION["decision"]
    assert matrix["juiz_sim_humano_sim"] == 12
    assert matrix["juiz_sim_humano_nao"] == 1
    assert matrix["juiz_nao_humano_sim"] == 1
    assert matrix["juiz_nao_humano_nao"] == 6
    assert matrix["acordos"] == 18
    assert matrix["desacordos"] == 2
    assert matrix["acuracia"] == 0.9
    assert decision["status"] == "juiz_adotado"
    assert decision["limiar"] == 17
    assert decision["rotulos"] == "revisado"


def test_judge_run_is_auditable_and_normalises_accents():
    assert normalizar_decisao("NÃO") == "NAO"
    assert normalizar_decisao("sim") == "SIM"
    assert normalizar_decisao("talvez") is None

    runs = VALIDATION["judge_runs"]
    assert len(runs) == 1
    run = json.loads((ROOT / runs[0]["arquivo"]).read_text(encoding="utf-8"))

    assert run["run_id"] == runs[0]["run_id"]
    assert run["status"] == "concluida"
    assert run["model"] == runs[0]["model"]
    assert run["temperature"] == 0
    assert len(run["cases"]) == 20
    assert {item["case_id"] for item in run["cases"]} == {
        case["case_id"] for case in VALIDATION["cases"]
    }
    assert all(item["resposta_bruta"] for item in run["cases"])
    assert all(item["justificativa"] for item in run["cases"])
    assert all(item["decisao"] in {"SIM", "NAO"} for item in run["cases"])


def test_disagreements_and_no_real_personal_data():
    rules = VALIDATION["disagreement_rules"]
    assert set(rules) >= {
        "problema_do_juiz",
        "problema_da_rubrica",
        "problema_do_rótulo",
    }
    disagreements = [
        case
        for case in VALIDATION["cases"]
        if case["juiz"]["decisao"] != case["humano"]["decisao"]
    ]
    assert len(disagreements) == len(VALIDATION["disagreements"])
    assert {
        item["case_id"]: item["classificacao"] for item in VALIDATION["disagreements"]
    } == {
        "dev-08-entrada-ambigua": "problema_da_rubrica",
        "syn-10-escolha-sem-especificacao": "problema_do_juiz",
    }
    for item in VALIDATION["disagreements"]:
        assert item["classificacao"] in {
            "problema_do_juiz",
            "problema_da_rubrica",
            "problema_do_rótulo",
        }
        assert item["justificativa"]

    serialised = json.dumps(VALIDATION, ensure_ascii=False)
    emails = re.findall(r"[\w.+-]+@[\w.-]+", serialised)
    assert emails and all(email.endswith("@example.test") for email in emails)


def test_run_files_are_versioned_next_to_validation():
    files = {path.name for path in RUNS_DIR.glob("*.json")}
    assert {Path(item["arquivo"]).name for item in VALIDATION["judge_runs"]} <= files
