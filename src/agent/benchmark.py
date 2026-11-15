"""Reproduz um benchmark de modelos usando prompts, ferramentas e casos do repo.

As ferramentas são simulações locais. Nenhuma chamada é feita à API da clínica.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI

from .app import SYSTEM_PROMPT, TOOLS

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "benchmarks" / "modelos.toml"
TOOL_NAMES = {item["function"]["name"] for item in TOOLS}
WRITE_TOOL = "confirmar_agendamento"
SYNTHETIC_PATIENT_ID = "00000000-0000-4000-8000-000000000001"
SYNTHETIC_PROFESSIONAL_ID = "00000000-0000-4000-8000-000000000002"
SYNTHETIC_START = "2027-03-19T09:00:00-03:00"
SYNTHETIC_END = "2027-03-19T10:00:00-03:00"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_config() -> tuple[dict[str, Any], list[dict[str, Any]], dict, list]:
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    benchmark = config["benchmark"]
    prompt_path = ROOT / benchmark["prompt"]
    cases_path = ROOT / benchmark["cases"]
    schema_path = ROOT / benchmark["schema"]
    prompt = prompt_path.read_text(encoding="utf-8")
    schema = _read_json(schema_path)
    cases = _read_json(cases_path)
    benchmark["prompt_text"] = prompt
    benchmark["prompt_sha256"] = _sha256(prompt.encode("utf-8"))
    benchmark["schema_sha256"] = _sha256(schema_path.read_bytes())
    benchmark["cases_sha256"] = _sha256(cases_path.read_bytes())
    return benchmark, config["models"], schema, cases


def _response_format(schema: dict) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "resposta_atendimento",
            "strict": True,
            "schema": schema,
        },
    }


def _valid_response(data: Any, schema: dict) -> bool:
    """Valida localmente o subconjunto de JSON Schema usado no contrato."""
    if not isinstance(data, dict) or set(data) != set(schema["required"]):
        return False
    for key in schema["required"]:
        definition = schema["properties"][key]
        value = data.get(key)
        if definition["type"] == "string":
            if not isinstance(value, str) or value not in definition.get("enum", [value]):
                return False
        elif definition["type"] == "object":
            if not isinstance(value, dict) or set(value) != set(definition["required"]):
                return False
            for child, child_definition in definition["properties"].items():
                child_value = value.get(child)
                if not isinstance(child_value, str):
                    return False
                if child_value not in child_definition.get("enum", [child_value]):
                    return False
        elif definition["type"] == "array":
            if not isinstance(value, list):
                return False
            item_schema = definition["items"]
            for item in value:
                if not isinstance(item, dict) or set(item) != set(item_schema["required"]):
                    return False
                for child, child_definition in item_schema["properties"].items():
                    child_value = item.get(child)
                    if not isinstance(child_value, str):
                        return False
                    if child_value not in child_definition.get("enum", [child_value]):
                        return False
    return True


def _valid_tool_arguments(name: str, arguments: Any) -> bool:
    if name not in TOOL_NAMES or not isinstance(arguments, dict):
        return False
    if name == "consultar_disponibilidade":
        return set(arguments).issubset({"patient_id"}) and all(
            isinstance(value, str) for value in arguments.values()
        )
    if name == WRITE_TOOL:
        required = {
            "patient_id",
            "professional_id",
            "agenda_inicio",
            "agenda_fim",
            "suspeita_paciente",
        }
        return set(arguments) == required and all(
            isinstance(value, str) for value in arguments.values()
        )
    return False


def _mock_tool(
    name: str, arguments: dict[str, Any], case: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retorna fixtures sintéticas e bloqueia qualquer escrita não autorizada."""
    if name == "consultar_disponibilidade":
        return (
            {
                "simulado": True,
                "value": [],
                "horarios_disponiveis": [
                    {
                        "inicio": SYNTHETIC_START,
                        "fim": SYNTHETIC_END,
                        "professional_id": SYNTHETIC_PROFESSIONAL_ID,
                    }
                ],
                "fonte_id": "agenda_disponibilidade_demo",
            },
            {"tipo": "api", "referencia": "agenda_disponibilidade_demo"},
        )

    if name == WRITE_TOOL:
        expected = {
            "patient_id": SYNTHETIC_PATIENT_ID,
            "professional_id": SYNTHETIC_PROFESSIONAL_ID,
            "agenda_inicio": SYNTHETIC_START,
            "agenda_fim": SYNTHETIC_END,
        }
        arguments_match = all(arguments.get(key) == value for key, value in expected.items())
        if not case["write_allowed"] or not arguments_match:
            return (
                {"simulado": True, "erro": "Escrita de teste bloqueada: confirmação ou opção não confere."},
                {"tipo": "api", "referencia": "gravacao_agendamento_demo"},
            )
        return (
            {
                "simulado": True,
                "resultado": "confirmado",
                "agendamento_id": "agendamento-demo-001",
                "inicio": SYNTHETIC_START,
                "fim": SYNTHETIC_END,
                "fonte_id": "gravacao_agendamento_demo",
            },
            {"tipo": "api", "referencia": "gravacao_agendamento_demo"},
        )
    return ({"simulado": True, "erro": "Ferramenta desconhecida."}, {})


def _source_check(data: Any, allowed_sources: list[dict]) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("fonte"), list):
        return False
    allowed = {(item["tipo"], item["referencia"]) for item in allowed_sources}
    returned = {
        (item.get("tipo"), item.get("referencia"))
        for item in data["fonte"]
        if isinstance(item, dict)
    }
    return bool(returned) and returned.issubset(allowed)


def _required_source_check(data: Any, required_sources: list[str]) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("fonte"), list):
        return False
    returned = {
        item.get("referencia")
        for item in data["fonte"]
        if isinstance(item, dict)
    }
    return set(required_sources).issubset(returned)


def _run_case(
    model: dict[str, Any],
    case: dict[str, Any],
    benchmark: dict[str, Any],
    schema: dict,
    repetition: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case_id": case["id"],
        "case_title": case["title"],
        "model": model["name"],
        "provider": model["provider"],
        "model_id": model["model_id"],
        "repetition": repetition,
        "expected_behavior": case["expected_behavior"],
        "expected_tool_calls": case["expected_tool_calls"],
        "expected_tool_arguments": case["expected_tool_arguments"],
        "required_sources": case["required_sources"],
        "tool_calls": [],
        "tool_results": [],
        "model_events": [],
        "test_context": case["context"],
        "test_input": case["input"],
        "allowed_sources": case["allowed_sources"],
        "model_calls": 0,
        "total_steps": 0,
        "tool_arguments_valid": True,
        "write_allowed": case["write_allowed"],
        "unsafe_write_attempt": False,
        "expected_sufficiency": case["expected_sufficiency"],
        "input_tokens": None,
        "output_tokens": None,
        "usage_complete": True,
        "token_budget_exceeded": False,
        "latency_seconds": None,
        "cost": None,
        "response_text": "",
        "response_json": None,
        "schema_valid": False,
        "sources_grounded": False,
        "required_sources_cited": False,
        "sufficiency_matches": False,
        "tool_behavior_matches": False,
        "tool_arguments_match_expected": False,
        "error": None,
    }
    try:
        client = OpenAI(
            api_key=os.environ[model["api_key_env"]],
            base_url=model["base_url"],
            timeout=benchmark["timeout_seconds"],
            max_retries=0,
        )
        messages = [
            {"role": "system", "content": benchmark["prompt_text"]},
            {
                "role": "user",
                "content": (
                    f"Contexto do caso de teste: {case['context']}\n\n"
                    f"IDs de fontes disponíveis no contexto: {', '.join(case['context_sources'])}.\n"
                    f"Mensagem do paciente: {case['input']}\n\n"
                    "Use somente os IDs de fonte apresentados no contexto ou devolvidos por ferramenta. "
                    "Os dados são fictícios e as ferramentas, "
                    "quando chamadas, são simuladas localmente."
                ),
            },
        ]
        model_calls = 0
        tool_calls = 0
        total_steps = 0
        total_tokens = 0
        tool_source_pairs = []
        started = time.perf_counter()
        termination = "completed"

        while True:
            if model_calls >= benchmark["max_model_calls"]:
                termination = "model_call_limit"
                break
            if total_steps >= benchmark["max_total_steps"]:
                termination = "step_limit"
                break
            if time.perf_counter() - started >= benchmark["timeout_seconds"]:
                termination = "timeout"
                break
            if total_tokens >= benchmark["max_total_tokens"]:
                termination = "token_limit"
                break
            remaining_tokens = benchmark["max_total_tokens"] - total_tokens

            call_started = time.perf_counter()
            response = client.chat.completions.create(
                model=model["model_id"],
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                response_format=_response_format(schema),
                temperature=benchmark["temperature"],
                max_tokens=min(benchmark["max_output_tokens"], remaining_tokens),
                timeout=max(
                    1,
                    benchmark["timeout_seconds"] - (time.perf_counter() - started),
                ),
            )
            model_calls += 1
            total_steps += 1
            result["model_calls"] = model_calls
            result["total_steps"] = total_steps
            call_latency = time.perf_counter() - call_started
            result["latency_seconds"] = (result["latency_seconds"] or 0.0) + call_latency
            usage = response.usage
            prompt_tokens = None
            completion_tokens = None
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None)
                if prompt_tokens is not None and completion_tokens is not None:
                    result["input_tokens"] = (result["input_tokens"] or 0) + prompt_tokens
                    result["output_tokens"] = (result["output_tokens"] or 0) + completion_tokens
                    total_tokens += prompt_tokens + completion_tokens
                    if total_tokens > benchmark["max_total_tokens"]:
                        result["token_budget_exceeded"] = True
                else:
                    result["usage_complete"] = False
            else:
                result["usage_complete"] = False

            message = response.choices[0].message
            event_tool_calls = [
                {
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                }
                for tool_call in (message.tool_calls or [])
            ]
            result["model_events"].append(
                {
                    "call": model_calls,
                    "latency_seconds": round(call_latency, 4),
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "finish_reason": response.choices[0].finish_reason,
                    "assistant_content": message.content,
                    "tool_calls_requested": event_tool_calls,
                }
            )
            messages.append(message.model_dump(exclude_none=True))
            if not message.tool_calls:
                result["response_text"] = message.content or ""
                break
            if result["token_budget_exceeded"]:
                termination = "token_limit"
                break

            for tool_call in message.tool_calls:
                if tool_calls >= benchmark["max_tool_calls"] or total_steps >= benchmark["max_total_steps"]:
                    termination = "tool_or_step_limit"
                    break
                tool_calls += 1
                total_steps += 1
                result["total_steps"] = total_steps
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = None
                arguments_valid = _valid_tool_arguments(name, arguments)
                result["tool_arguments_valid"] = result["tool_arguments_valid"] and arguments_valid
                result["tool_calls"].append(
                    {"name": name, "arguments": arguments, "arguments_valid": arguments_valid}
                )
                if name == WRITE_TOOL:
                    expected_write_args = next(
                        (
                            item
                            for expected_name, item in zip(
                                case["expected_tool_calls"],
                                case["expected_tool_arguments"],
                            )
                            if expected_name == WRITE_TOOL
                        ),
                        {},
                    )
                    args_match = isinstance(arguments, dict) and all(
                        arguments.get(key) == value
                        for key, value in expected_write_args.items()
                    )
                    if not case["write_allowed"] or not args_match or not arguments_valid:
                        result["unsafe_write_attempt"] = True
                if arguments_valid:
                    tool_result, source = _mock_tool(name, arguments, case)
                    if source:
                        tool_source_pairs.append(source)
                else:
                    tool_result = {"simulado": True, "erro": "Argumentos ou ferramenta inválidos."}
                result["tool_results"].append(
                    {
                        "id": tool_call.id,
                        "name": name,
                        "arguments": arguments,
                        "result": tool_result,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
            if termination != "completed":
                break

        result["termination"] = termination
        if not result["usage_complete"]:
            result["input_tokens"] = None
            result["output_tokens"] = None
        if result["latency_seconds"] is not None:
            result["latency_seconds"] = round(result["latency_seconds"], 4)
        try:
            result["response_json"] = json.loads(result["response_text"])
        except (json.JSONDecodeError, TypeError):
            result["response_json"] = None
        result["schema_valid"] = _valid_response(result["response_json"], schema)
        result["sources_grounded"] = _source_check(
            result["response_json"], case["allowed_sources"]
        )
        result["required_sources_cited"] = _required_source_check(
            result["response_json"], case["required_sources"]
        )
        result["sufficiency_matches"] = (
            isinstance(result["response_json"], dict)
            and result["response_json"].get("suficiencia") == case["expected_sufficiency"]
        )
        actual_tool_names = [item["name"] for item in result["tool_calls"]]
        actual_tool_args = [item.get("arguments") for item in result["tool_calls"]]
        expected_tool_args = case["expected_tool_arguments"]
        result["tool_arguments_match_expected"] = (
            len(actual_tool_args) == len(expected_tool_args)
            and all(
                isinstance(actual, dict)
                and all(actual.get(key) == value for key, value in expected.items())
                for actual, expected in zip(actual_tool_args, expected_tool_args)
            )
        )
        result["tool_behavior_matches"] = (
            actual_tool_names == case["expected_tool_calls"]
            and result["tool_arguments_match_expected"]
        )
        if result["input_tokens"] is not None and result["output_tokens"] is not None:
            result["cost"] = round(
                (
                    result["input_tokens"] * model["input_price_per_million"]
                    + result["output_tokens"] * model["output_price_per_million"]
                )
                / 1_000_000,
                10,
            )
        result["sources_from_tools"] = tool_source_pairs
    except Exception as error:  # retain provider failures as benchmark evidence
        result["error"] = f"{type(error).__name__}: {str(error)[:500]}"
        result["termination"] = "provider_or_request_error"
    return result


def _summarize(results: list[dict[str, Any]], models: list[dict], daily_volume: int | None) -> list[dict]:
    summary = []
    for model in models:
        rows = [row for row in results if row["model"] == model["name"]]
        completed = [row for row in rows if not row["error"]]
        latencies = [row["latency_seconds"] for row in completed if row["latency_seconds"] is not None]
        token_rows = [
            row for row in completed
            if row["input_tokens"] is not None and row["output_tokens"] is not None
        ]
        cost_complete = (
            len(token_rows) == len(completed)
            and all(row["usage_complete"] for row in completed)
            and bool(completed)
        )
        total_cost = sum(row["cost"] for row in token_rows) if cost_complete else None
        summary.append(
            {
                "model": model["name"],
                "provider": model["provider"],
                "model_id": model["model_id"],
                "runs": len(rows),
                "errors": sum(bool(row["error"]) for row in rows),
                "schema_valid": sum(row["schema_valid"] for row in completed),
                "tools_expected": sum(row["tool_behavior_matches"] for row in completed),
                "sources_grounded": sum(row["sources_grounded"] for row in completed),
                "required_sources_cited": sum(row["required_sources_cited"] for row in completed),
                "sufficiency_matches": sum(row["sufficiency_matches"] for row in completed),
                "tool_argument_schema_valid": sum(row["tool_arguments_valid"] for row in completed),
                "unsafe_writes": sum(row["unsafe_write_attempt"] for row in rows),
                "token_budget_exceeded": sum(row["token_budget_exceeded"] for row in completed),
                "input_tokens": sum(row["input_tokens"] or 0 for row in token_rows) if token_rows else None,
                "output_tokens": sum(row["output_tokens"] or 0 for row in token_rows) if token_rows else None,
                "latency_median_seconds": round(statistics.median(latencies), 4) if latencies else None,
                "cost_total": round(total_cost, 10) if total_cost is not None else None,
                "cost_per_100_runs": round(total_cost * 100 / len(completed), 8) if total_cost is not None else None,
                "cost_semester_projection": (
                    round(total_cost * daily_volume * 182 / len(completed), 8)
                    if total_cost is not None and daily_volume is not None
                    else None
                ),
                "currency": model["currency"],
                "all_costs_observed": cost_complete,
            }
        )
    return summary


def _write_reports(
    results: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    benchmark: dict,
    models: list[dict],
    output_dir: Path,
    daily_volume: int | None,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
    json_path = output_dir / f"{run_id}.json"
    csv_path = output_dir / f"{run_id}.csv"
    md_path = output_dir / f"{run_id}.md"
    details = {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset": "casos sintéticos locais; nenhuma API da clínica é acessada",
        "repetitions": max((row["repetition"] for row in results), default=0),
        "daily_interactions_for_projection": daily_volume,
        "fixed_inputs": {
            "system_prompt_sha256": benchmark["prompt_sha256"],
            "schema_sha256": benchmark["schema_sha256"],
            "cases_sha256": benchmark["cases_sha256"],
            "tool_names": sorted(TOOL_NAMES),
            "tool_schema_sha256": _sha256(
                json.dumps(TOOLS, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ),
            "limits": {
                key: benchmark[key]
                for key in [
                    "max_model_calls", "max_tool_calls", "max_total_steps",
                    "max_total_tokens", "timeout_seconds", "max_output_tokens", "temperature"
                ]
            },
            "request": {"tool_choice": "auto", "response_format": "strict JSON Schema"},
        },
        "models": [
            {key: value for key, value in model.items() if key != "api_key_env"}
            for model in models
        ],
        "summary": summary,
        "results": results,
        "manual_review": "Preencher os campos de avaliação humana no CSV; métricas automáticas não escolhem sozinhas o modelo.",
    }
    json_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_fields = [
        "case_id", "case_title", "model", "provider", "model_id", "repetition", "model_calls", "total_steps",
        "expected_behavior", "expected_tool_calls", "expected_tool_arguments", "required_sources", "tool_calls", "tool_arguments_valid",
        "tool_arguments_match_expected",
        "tool_behavior_matches", "schema_valid", "sources_grounded", "required_sources_cited", "expected_sufficiency",
        "response_json", "response_text", "unsafe_write_attempt", "input_tokens", "output_tokens", "usage_complete", "token_budget_exceeded",
        "latency_seconds", "cost", "currency", "termination", "error",
        "human_accuracy_0_2", "human_clarity_0_2", "human_grounding_0_2", "human_safety_0_2", "reviewer_notes",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            row = {**row, "currency": next(m["currency"] for m in models if m["name"] == row["model"])}
            writer.writerow(row)

    lines = [
        "# Resultado do benchmark de modelos",
        "",
        f"Execução: `{run_id}`. Dataset totalmente sintético; as ferramentas são simuladas localmente.",
        "",
        "| Modelo e endpoint | Schema de resposta | Schema dos argumentos | Tool calls esperadas | Fontes permitidas/obrigatórias | Suficiência correta | Escritas inseguras | Limite de tokens excedido | Tokens entrada/saída | Latência mediana | Custo total | Custo por 100 execuções | Semestre projetado |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        total = row["runs"] - row["errors"]
        latency = f"{row['latency_median_seconds']} s" if row["latency_median_seconds"] is not None else "n/d"
        cost = f"{row['cost_total']} {row['currency']}" if row["cost_total"] is not None else "n/d"
        cost_100 = f"{row['cost_per_100_runs']} {row['currency']}" if row["cost_per_100_runs"] is not None else "n/d"
        semester_cost = (
            f"{row['cost_semester_projection']} {row['currency']}"
            if row["cost_semester_projection"] is not None
            else "n/d"
        )
        input_tokens = row["input_tokens"] if row["input_tokens"] is not None else "n/d"
        output_tokens = row["output_tokens"] if row["output_tokens"] is not None else "n/d"
        lines.append(
            f"| {row['model']} ({row['provider']} / `{row['model_id']}`) | {row['schema_valid']}/{total} | "
            f"{row['tool_argument_schema_valid']}/{total} | {row['tools_expected']}/{total} | "
            f"{row['sources_grounded']}/{total} · {row['required_sources_cited']}/{total} | "
            f"{row['sufficiency_matches']}/{total} | {row['unsafe_writes']} | {row['token_budget_exceeded']} | "
            f"{input_tokens}/{output_tokens} | {latency} | {cost} | {cost_100} | {semester_cost} |"
        )
    lines.extend(
        [
            "",
            "## Leitura e limites",
            "",
            "- As colunas automáticas conferem schema, comportamento esperado das ferramentas, referências de fonte, suficiência e tentativa de escrita sem confirmação.",
            "- O CSV inclui campos para revisão humana de correção, clareza, sustentação por fonte e segurança. Completem essa revisão antes de escolher um modelo.",
            "- Escala humana: 0 = falhou/gerou risco; 1 = parcialmente correto ou exigiu correção; 2 = atendeu ao esperado sem inventar informação.",
            "- Custo usa tokens informados pelo endpoint e os preços de `benchmarks/modelos.toml`; preço não informado pelo endpoint resulta em custo indisponível, nunca estimado por tokenizer.",
            "- O valor calculado é uma estimativa de tokens cobrados conforme tarifa configurada; cache, tarifas extras, impostos e arredondamento da fatura do provedor podem alterar o total.",
            "- Uma projeção semestral só é calculada se `--daily-volume` for informado; ela representa 182 dias e depende do volume fornecido pelo grupo.",
            "- Esta execução não mede benefício para pacientes, profissionais ou operação clínica. Não usa dados reais nem acessa sistema da clínica.",
            "",
            f"Hashes: prompt `{benchmark['prompt_sha256']}`, schema `{benchmark['schema_sha256']}`, casos `{benchmark['cases_sha256']}`.",
        ]
    )
    if daily_volume is not None:
        lines.insert(-1, f"Projeção semestral para {daily_volume} interações/dia (182 dias): custos por modelo constam no JSON.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara modelos no benchmark sintético do projeto.")
    parser.add_argument("--repetitions", type=int, default=1, help="repetições por caso e modelo (padrão: 1)")
    parser.add_argument("--daily-volume", type=int, help="volume diário explícito para projeção semestral")
    parser.add_argument("--model", action="append", dest="selected_models", help="nome exato do modelo; pode repetir")
    parser.add_argument("--dry-run", action="store_true", help="mostra configuração sem chamar provedores")
    parser.add_argument("--output-dir", help="pasta para relatórios; padrão definido no TOML")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions deve ser ao menos 1")
    if args.daily_volume is not None and args.daily_volume < 0:
        parser.error("--daily-volume não pode ser negativo")

    load_dotenv(ROOT / ".env")
    benchmark, models, schema, cases = _read_config()
    if args.selected_models:
        requested = set(args.selected_models)
        models = [model for model in models if model["name"] in requested]
        unknown = requested - {model["name"] for model in models}
        if unknown:
            parser.error(f"modelos não configurados: {', '.join(sorted(unknown))}")
    if not models:
        parser.error("nenhum modelo configurado")

    print("Comparação com a mesma versão de prompt, schema, ferramentas, casos e limites.")
    print(f"Casos: {len(cases)} | repetições: {args.repetitions} | ferramentas simuladas, sem acesso à clínica.")
    for model in models:
        print(f"- {model['name']}: {model['provider']} / {model['model_id']} ({model['base_url']})")
    if args.dry_run:
        print("Dry run: nenhum provedor foi chamado.")
        return 0

    missing = sorted({model["api_key_env"] for model in models if not os.getenv(model["api_key_env"])})
    if missing:
        print("Configure estas chaves em .env: " + ", ".join(missing), file=sys.stderr)
        return 2

    results = []
    for model in models:
        for case in cases:
            for repetition in range(1, args.repetitions + 1):
                print(f"Executando {model['name']} · {case['id']} · tentativa {repetition}...")
                row = _run_case(model, case, benchmark, schema, repetition)
                results.append(row)
                if row["error"]:
                    print(f"  Falha registrada: {row['error']}", file=sys.stderr)

    summary = _summarize(results, models, args.daily_volume)
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / benchmark["results_dir"]
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    json_path, csv_path, md_path = _write_reports(
        results, summary, benchmark, models, output_dir, args.daily_volume
    )
    print(f"Relatório Markdown: {md_path}")
    print(f"Resultados detalhados: {json_path}")
    print(f"Planilha para avaliação humana: {csv_path}")
    return 1 if any(row["error"] for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
