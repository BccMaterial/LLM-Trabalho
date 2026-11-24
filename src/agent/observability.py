import atexit
import hashlib
import json
import os
import tomllib
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import Span, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

SERVICE_NAME_VALUE = "llm-trabalho-agent"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_provider: TracerProvider | None = None
_capture_synthetic_trace_payloads: ContextVar[bool] = ContextVar(
    "capture_synthetic_trace_payloads",
    default=False,
)


@dataclass(frozen=True)
class EvaluationTraceContext:
    run_id: str
    case_id: str
    version: str
    commit: str
    capture_synthetic_payloads: bool = False


def synthetic_trace_payloads_enabled() -> bool:
    return _capture_synthetic_trace_payloads.get()


@lru_cache(maxsize=1)
def system_version() -> str:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)["project"]["version"]


@lru_cache(maxsize=1)
def agent_prompt_sha256() -> str:
    prompt_path = PROJECT_ROOT / "src" / "prompts" / "atendente_v1.txt"
    return hashlib.sha256(prompt_path.read_bytes()).hexdigest()


def configure_tracing() -> TracerProvider:
    global _provider
    if _provider is not None:
        return _provider

    version = system_version()
    provider = TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: SERVICE_NAME_VALUE,
                SERVICE_VERSION: version,
            }
        )
    )
    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4317",
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)
    if trace.get_tracer_provider() is not provider:
        provider.shutdown()
        raise RuntimeError("O provedor OpenTelemetry já foi configurado.")
    _provider = provider
    atexit.register(provider.shutdown)
    return provider


def tracer():
    return trace.get_tracer("llm-trabalho.agent", system_version())


def mark_span_error(span: Span, error: Exception) -> None:
    span.set_attribute("error.type", type(error).__name__)
    span.set_status(Status(StatusCode.ERROR))


def set_token_usage(span: Span, usage: Any) -> None:
    if usage is None:
        return
    for attribute, candidates in (
        ("gen_ai.usage.input_tokens", ("input_tokens", "prompt_tokens")),
        ("gen_ai.usage.output_tokens", ("output_tokens", "completion_tokens")),
    ):
        value = next(
            (
                getattr(usage, name, None)
                for name in candidates
                if getattr(usage, name, None) is not None
            ),
            None,
        )
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            span.set_attribute(attribute, value)


def set_root_result(
    span: Span,
    result: Any,
    *,
    capture_synthetic_payloads: bool = False,
) -> None:
    if not isinstance(result, dict):
        return

    termination_reason = result.get("termination_reason")
    if isinstance(termination_reason, str):
        span.set_attribute("app.termination.reason", termination_reason)

    error_class = result.get("error_class")
    if isinstance(error_class, str):
        span.set_attribute("app.error.class", error_class)

    error_kind = result.get("error_kind")
    if isinstance(error_kind, str):
        span.set_attribute("app.error.kind", error_kind)

    total_tokens = result.get("total_model_tokens")
    if isinstance(total_tokens, int) and total_tokens >= 0:
        span.set_attribute("app.usage.total_tokens", total_tokens)

    tool_results = result.get("tool_results") or []
    tool_names = sorted(
        {
            item["name"]
            for item in tool_results
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
    )
    if tool_names:
        span.set_attribute("app.tools.names", tool_names)

    policy_references = []
    for item in tool_results:
        if not isinstance(item, dict) or item.get("name") != "consultar_politica":
            continue
        tool_result = item.get("result")
        if not isinstance(tool_result, dict):
            continue
        for policy in tool_result.get("resultados", []):
            if not isinstance(policy, dict):
                continue
            reference = [
                policy.get("documento"),
                policy.get("versao"),
                policy.get("trecho"),
            ]
            if all(isinstance(part, str) and part for part in reference):
                policy_references.append(reference)
    if policy_references:
        span.set_attribute(
            "app.context.policy.references",
            json.dumps(sorted(policy_references), ensure_ascii=True),
        )

    approval_decision = result.get("approval_decision")
    if isinstance(approval_decision, str):
        span.set_attribute("app.approval.decision", approval_decision)
    approval_version = result.get("proposal_version")
    if isinstance(approval_version, int) and approval_version >= 0:
        span.set_attribute("app.approval.proposal_version", approval_version)

    interrupts = result.get("__interrupt__") or []
    if interrupts:
        span.set_attribute("app.approval.required", True)
        interrupt_value = getattr(interrupts[0], "value", None)
        if isinstance(interrupt_value, dict):
            version = interrupt_value.get("proposal_version")
            if isinstance(version, int) and version >= 0:
                span.set_attribute("app.approval.proposal_version", version)

    approval_events = result.get("approval_events")
    if capture_synthetic_payloads and isinstance(approval_events, list):
        span.set_attribute(
            "app.evaluation.approvals",
            json.dumps(approval_events, ensure_ascii=True, sort_keys=True),
        )

    output = result.get("structured_response")
    if not isinstance(output, dict):
        return
    if capture_synthetic_payloads:
        span.set_attribute(
            "app.evaluation.output",
            json.dumps(output, ensure_ascii=True, sort_keys=True),
        )
    output_result = output.get("resultado")
    if isinstance(output_result, dict):
        for key, attribute in (
            ("status", "app.output.status"),
            ("acao", "app.output.action"),
        ):
            value = output_result.get(key)
            if isinstance(value, str):
                span.set_attribute(attribute, value)
    sufficiency = output.get("suficiencia")
    if isinstance(sufficiency, str):
        span.set_attribute("app.output.sufficiency", sufficiency)
    sources = output.get("fonte") or []
    source_types = sorted(
        {
            source["tipo"]
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("tipo"), str)
        }
    )
    if source_types:
        span.set_attribute("app.output.source_types", source_types)


def invoke_agent(
    graph: Any,
    graph_input: Any,
    config: dict,
    *,
    mode: str,
    turn_index: int,
    approval_decision: str | None = None,
    evaluation_context: EvaluationTraceContext | None = None,
) -> Any:
    version = system_version()
    attributes = {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": SERVICE_NAME_VALUE,
        "app.system.version": version,
        "app.prompt.sha256": agent_prompt_sha256(),
        "app.execution.mode": mode,
        "app.turn.index": turn_index,
        "app.approval.resumed": approval_decision is not None,
    }
    capture_synthetic_payloads = bool(
        evaluation_context and evaluation_context.capture_synthetic_payloads
    )
    attributes["app.evaluation.payload_capture"] = capture_synthetic_payloads
    if approval_decision is not None:
        attributes["app.approval.resume_decision"] = (
            approval_decision
            if approval_decision in {"approve", "reject", "edit", "invalid"}
            else "other"
        )
    if evaluation_context is not None:
        attributes.update(
            {
                "app.evaluation.run_id": evaluation_context.run_id,
                "app.evaluation.case_id": evaluation_context.case_id,
                "app.evaluation.version": evaluation_context.version,
                "app.evaluation.commit": evaluation_context.commit,
            }
        )

    with tracer().start_as_current_span(
        "invoke_agent",
        attributes=attributes,
    ) as span:
        capture_token = _capture_synthetic_trace_payloads.set(
            capture_synthetic_payloads
        )
        try:
            if capture_synthetic_payloads and isinstance(graph_input, dict):
                user_messages = [
                    {"role": "user", "content": message["content"]}
                    for message in graph_input.get("messages", [])
                    if isinstance(message, dict)
                    and message.get("role") == "user"
                    and isinstance(message.get("content"), str)
                ]
                span.set_attribute(
                    "app.evaluation.input",
                    json.dumps(user_messages, ensure_ascii=True),
                )
            result = graph.invoke(graph_input, config)
        except Exception as error:
            mark_span_error(span, error)
            raise
        else:
            set_root_result(
                span,
                result,
                capture_synthetic_payloads=capture_synthetic_payloads,
            )
            return result
        finally:
            _capture_synthetic_trace_payloads.reset(capture_token)
