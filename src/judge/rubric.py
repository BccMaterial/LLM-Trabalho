"""Regras puras da rubrica binária validada na Issue #56.

Nenhuma função deste módulo chama LLM. Elas leem as anotações versionadas em
``evals/`` e recalculam matriz, decisão e prompt cego exatamente como na
validação original; o código apenas mudou de ``scripts/validate_judge.py``.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
VALIDATION_PATH = ROOT / "evals" / "judge_validation.json"
PROMPT_PATH = ROOT / "evals" / "judge_prompt.txt"
RUNS_DIR = ROOT / "evals" / "judge_runs"
DECISOES = {"SIM", "NAO"}
JUDGE_TEMPERATURE = 0
JUDGE_MAX_TOKENS = 300


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_pre_registration(validation: dict[str, Any]) -> None:
    pre = validation["pre_registration"]
    cases = validation["cases"]
    negatives = sum(case["humano"]["decisao"] == "NAO" for case in cases)
    assert pre["registered_before_judge_call"] is True, "limiar não foi pré-registrado"
    assert pre["sample_size"] == len(cases) == 20, "amostra não tem 20 saídas"
    assert pre["threshold"] == 17, "limiar foi alterado depois do pré-registro"
    assert pre["threshold_ratio"] == 0.85, "razão do limiar foi alterada"
    assert pre["threshold"] == round(pre["sample_size"] * pre["threshold_ratio"])
    assert negatives >= 7, "amostra não tem pelo menos 7 rótulos NÃO"
    labels = validation["labels"]
    assert (
        labels["status"] == "revisado"
    ), "os rótulos humanos ainda não foram revisados"
    assert labels.get("reviewed_by"), "revisor humano não registrado"
    assert labels.get("reviewed_at"), "data da revisão humana não registrada"
    assert all(
        case["humano"]["decisao"] in DECISOES and case["humano"]["justificativa"]
        for case in cases
    ), "rótulos humanos incompletos"


def build_prompt(case: dict[str, Any]) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    saida = json.dumps(case["saida"], ensure_ascii=False, sort_keys=True, indent=2)
    return (
        template.replace("__PEDIDO__", case["pedido"])
        .replace("__CONTEXTO__", case["contexto_ferramentas"])
        .replace("__SAIDA__", saida)
    )


def normalizar_decisao(value: Any) -> str | None:
    """Aceita variações de caixa e acento, mantendo apenas SIM/NAO no arquivo."""
    if not isinstance(value, str):
        return None
    plain = "".join(
        char
        for char in unicodedata.normalize("NFD", value.strip().upper())
        if unicodedata.category(char) != "Mn"
    )
    return plain if plain in DECISOES else None


def parse_judge_response(raw: str) -> dict[str, Any]:
    """Aceita JSON puro ou JSON dentro de uma cerca de código Markdown."""
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("juiz não retornou um JSON") from error
        parsed = json.loads(candidate[start : end + 1])
    decisao = (
        normalizar_decisao(parsed.get("decisao")) if isinstance(parsed, dict) else None
    )
    if decisao is None:
        raise ValueError("juiz retornou decisão fora da rubrica binária")
    parsed["decisao"] = decisao
    if (
        not isinstance(parsed.get("justificativa"), str)
        or not parsed["justificativa"].strip()
    ):
        raise ValueError("juiz não justificou a decisão")
    if not isinstance(parsed.get("criterios", []), list):
        raise ValueError("juiz retornou critérios em formato inválido")
    return parsed


def compute_matrix(validation: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "juiz_sim_humano_sim": 0,
        "juiz_sim_humano_nao": 0,
        "juiz_nao_humano_sim": 0,
        "juiz_nao_humano_nao": 0,
    }
    labels: dict[str, str] = {}
    for case in validation["cases"]:
        if "juiz" not in case:
            raise ValueError(f"caso {case['case_id']} ainda não tem julgamento")
        labels[case["case_id"]] = case["humano"]["decisao"]
        key = (
            f"juiz_{case['juiz']['decisao'].lower()}_humano_"
            f"{case['humano']['decisao'].lower()}"
        )
        counts[key] += 1
    agreements = counts["juiz_sim_humano_sim"] + counts["juiz_nao_humano_nao"]
    disagreements = counts["juiz_sim_humano_nao"] + counts["juiz_nao_humano_sim"]
    total = sum(counts.values())
    return {
        **counts,
        "verdadeiros_positivos": counts["juiz_sim_humano_sim"],
        "falsos_positivos": counts["juiz_sim_humano_nao"],
        "verdadeiros_negativos": counts["juiz_nao_humano_nao"],
        "falsos_negativos": counts["juiz_nao_humano_sim"],
        "total": total,
        "acordos": agreements,
        "desacordos": disagreements,
        "acuracia": round(agreements / total, 4),
        "human_labels": labels,
    }


def build_decision(
    validation: dict[str, Any], matrix: dict[str, Any]
) -> dict[str, Any]:
    threshold = validation["pre_registration"]["threshold"]
    adopted = matrix["acordos"] >= threshold
    labels = validation["labels"]
    reviewers = ", ".join(labels["reviewed_by"])
    return {
        "status": "juiz_adotado" if adopted else "juiz_nao_adotado",
        "acordos": matrix["acordos"],
        "limiar": threshold,
        "regra": "acordos >= limiar, fixado antes da medição",
        "rotulos": labels["status"],
        "observacao": f"Rótulos revisados por {reviewers} em {labels['reviewed_at']}.",
    }


def judge_adopted() -> bool:
    validation = read_json(VALIDATION_PATH)
    matrix = compute_matrix(validation)
    return build_decision(validation, matrix)["status"] == "juiz_adotado"
