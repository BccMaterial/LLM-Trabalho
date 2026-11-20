import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "evals" / "golden_dataset.json"


def test_golden_dataset_has_required_shape_and_coverage():
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = dataset["cases"]

    assert len(cases) >= 20
    assert dataset["normative_contract"] == "src/agent/output_contract.py"
    assert dataset["entrypoint"] == "src.agent.cli.run_scheduling_case"
    assert len(dataset["reviewers"]) == 3

    required = {"id", "origem", "classe", "por_que_existe", "entrada", "esperado"}
    classes = Counter(case["classe"] for case in cases)
    assert all(required <= case.keys() for case in cases)
    assert set(classes) >= {
        "confirmacao_e_gravacao",
        "falha_de_ferramenta",
        "divergencia_de_estado",
    }
    assert all(
        classes[name] >= 2
        for name in {
            "confirmacao_e_gravacao",
            "falha_de_ferramenta",
            "divergencia_de_estado",
        }
    )
    assert {case["origem"] for case in cases} == {"desenvolvimento", "sintetico"}


def test_development_cases_reference_existing_logs_and_synthetic_cases_are_reviewed():
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    for case in dataset["cases"]:
        if case["origem"] == "desenvolvimento":
            evidence = case["evidencia"]
            assert (ROOT / evidence["arquivo"]).is_file()
            assert evidence["tipo"] == "log_versionado"
        else:
            assert case["revisao"]["revisores"] == "os três contribuidores"


def test_dataset_does_not_claim_production_data_or_unknown_tools():
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    allowed_tools = {
        "consultar_profissionais",
        "consultar_disponibilidade",
        "confirmar_agendamento",
        "consultar_politica",
    }
    assert all(case["origem"] != "producao" for case in dataset["cases"])
    assert all(
        set(case["esperado"]["ferramentas"]) <= allowed_tools
        for case in dataset["cases"]
    )
