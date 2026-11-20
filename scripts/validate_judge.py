"""Gera e confere a matriz juiz × humano da avaliação de clareza e utilidade.

O limiar e os rótulos humanos são pré-registrados em ``judge_validation.json``.
A chamada ao LLM grava respostas brutas em ``evals/judge_runs/``; nenhuma chamada
altera o limiar, os rótulos ou a decisão. ``--apply-run`` consolida uma rodada
já executada e ``--dry-run`` apenas reconfere os dados versionados.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
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
        key = f"juiz_{case['juiz']['decisao'].lower()}_humano_{case['humano']['decisao'].lower()}"
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


def call_judge() -> Path:
    import os

    from openai import OpenAI

    load_dotenv(ROOT / ".env")
    missing = [
        name
        for name in ("LLM_BASE_URL", "OPENAI_API_KEY", "LLM_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(f"variáveis ausentes para o juiz: {', '.join(missing)}")

    validation = read_json(VALIDATION_PATH)
    verify_pre_registration(validation)
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")

    client = OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=60,
        max_retries=2,
    )
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )
    path = RUNS_DIR / f"{run_id}.json"
    run: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": os.environ["LLM_MODEL"],
        "provider": "endpoint OpenAI-compatível configurado em LLM_BASE_URL",
        "prompt_file": "evals/judge_prompt.txt",
        "prompt_sha256": sha256(prompt_text),
        "temperature": JUDGE_TEMPERATURE,
        "max_tokens": JUDGE_MAX_TOKENS,
        "status": "em_andamento",
        "cases": [],
    }
    write_json(path, run)

    for case in validation["cases"]:
        prompt = build_prompt(case)
        parsed = None
        raw = ""
        for attempt in range(2):
            response = client.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                messages=[{"role": "user", "content": prompt}],
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
            )
            raw = response.choices[0].message.content or ""
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
