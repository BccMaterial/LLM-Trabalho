import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from src.agent import tools
from src.agent.integrations import llm
from src.agent.observability import EvaluationTraceContext, invoke_agent


@pytest.fixture(scope="module")
def span_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    provider.shutdown()


@pytest.mark.parametrize("capture_payloads", [False, True])
def test_agent_trace_captures_genai_spans(
    monkeypatch,
    span_exporter,
    capture_payloads,
):
    private_text = "paciente-identificavel"
    policy_result = {
        "consulta": private_text,
        "suficiencia": "suficiente",
        "resultados": [
            {
                "conteudo": private_text,
                "documento": "policy-42",
                "versao": "v3",
                "trecho": "chunk-7",
            }
        ],
    }
    response = SimpleNamespace(
        model="model-demo",
        usage=SimpleNamespace(prompt_tokens=21, completion_tokens=8),
        choices=[SimpleNamespace(finish_reason="tool_calls")],
    )
    monkeypatch.setenv("LLM_MODEL", "model-requested")
    monkeypatch.setattr(llm, "_request_with_retry", lambda *args, **kwargs: response)
    monkeypatch.setattr(
        tools,
        "_execute_tool",
        lambda *args, **kwargs: policy_result,
    )

    class Graph:
        def invoke(self, graph_input, config):
            llm.request_with_retry(object(), [{"content": private_text}])
            tool_result = tools.execute_tool(
                object(),
                "consultar_politica",
                {"pergunta": private_text},
            )
            return {
                "termination_reason": "normal_completion",
                "error_class": None,
                "total_model_tokens": 29,
                "tool_results": [
                    {
                        "name": "consultar_politica",
                        "arguments": {"pergunta": private_text},
                        "result": tool_result,
                    }
                ],
                "approval_decision": "approve",
                "approval_events": [
                    {
                        "actor_id": "synthetic-patient",
                        "action": "confirmar_agendamento",
                        "decision": "approve",
                        "occurred_at": "2026-01-01T00:00:00+00:00",
                        "proposal_version": 2,
                        "arguments": {"agenda_inicio": private_text},
                    }
                ],
                "proposal_version": 2,
                "structured_response": {
                    "resultado": {
                        "status": "revisao_humana_necessaria",
                        "acao": "encaminhada",
                        "mensagem": private_text,
                    },
                    "fonte": [{"tipo": "politica", "referencia": private_text}],
                    "suficiencia": "insuficiente",
                },
            }

    span_exporter.clear()
    invoke_agent(
        Graph(),
        {"messages": [{"role": "user", "content": private_text}]},
        {},
        mode="case",
        turn_index=1,
        evaluation_context=EvaluationTraceContext(
            run_id="run-demo",
            case_id="case-demo",
            version="issue-61",
            commit="a" * 40,
            capture_synthetic_payloads=capture_payloads,
        ),
    )

    spans = span_exporter.get_finished_spans()
    spans_by_name = {span.name: span for span in spans}
    assert set(spans_by_name) == {"invoke_agent", "chat", "execute_tool"}
    root = spans_by_name["invoke_agent"]
    chat = spans_by_name["chat"]
    tool = spans_by_name["execute_tool"]
    assert chat.parent.span_id == root.context.span_id
    assert tool.parent.span_id == root.context.span_id
    assert root.attributes["app.system.version"] == "0.1.0"
    prompt_sha256 = hashlib.sha256(
        (
            Path(__file__).resolve().parents[3] / "src" / "prompts" / "atendente_v1.txt"
        ).read_bytes()
    ).hexdigest()
    assert root.attributes["app.prompt.sha256"] == prompt_sha256
    assert root.attributes["app.evaluation.run_id"] == "run-demo"
    assert root.attributes["app.evaluation.case_id"] == "case-demo"
    assert root.attributes["app.evaluation.version"] == "issue-61"
    assert root.attributes["app.evaluation.commit"] == "a" * 40
    assert root.attributes["app.termination.reason"] == "normal_completion"
    assert root.attributes["app.approval.decision"] == "approve"
    assert root.attributes["app.output.status"] == "revisao_humana_necessaria"
    assert root.attributes["app.output.source_types"] == ("politica",)
    assert json.loads(root.attributes["app.context.policy.references"]) == [
        ["policy-42", "v3", "chunk-7"]
    ]
    assert chat.attributes["gen_ai.request.model"] == "model-requested"
    assert chat.attributes["gen_ai.response.model"] == "model-demo"
    assert chat.attributes["gen_ai.usage.input_tokens"] == 21
    assert chat.attributes["gen_ai.usage.output_tokens"] == 8
    assert tool.attributes["gen_ai.tool.name"] == "consultar_politica"

    if capture_payloads:
        assert json.loads(root.attributes["app.evaluation.input"]) == [
            {"role": "user", "content": private_text}
        ]
        assert (
            json.loads(root.attributes["app.evaluation.output"])["resultado"][
                "mensagem"
            ]
            == private_text
        )
        approval = json.loads(root.attributes["app.evaluation.approvals"])[0]
        assert approval["actor_id"] == "synthetic-patient"
        assert approval["decision"] == "approve"
        assert approval["arguments"] == {"agenda_inicio": private_text}
        assert approval["occurred_at"] == "2026-01-01T00:00:00+00:00"
        assert json.loads(tool.attributes["app.evaluation.tool.arguments"]) == {
            "pergunta": private_text
        }
        assert json.loads(tool.attributes["app.evaluation.tool.result"]) == (
            policy_result
        )
    else:
        assert "app.evaluation.input" not in root.attributes
        assert "app.evaluation.output" not in root.attributes
        assert "app.evaluation.approvals" not in root.attributes
        assert "app.evaluation.tool.arguments" not in tool.attributes
        assert "app.evaluation.tool.result" not in tool.attributes

    exported_attributes = json.dumps(
        [dict(span.attributes) for span in spans],
        ensure_ascii=True,
    )
    assert (private_text in exported_attributes) is capture_payloads


def test_tool_exception_is_signaled_without_exporting_its_message(
    monkeypatch,
    span_exporter,
):
    private_text = "erro-com-dado-clinico"

    def fail_tool(*args, **kwargs):
        raise RuntimeError(private_text)

    monkeypatch.setattr(tools, "_execute_tool", fail_tool)
    span_exporter.clear()

    with pytest.raises(RuntimeError, match=private_text):
        invoke_agent(
            _ToolGraph(private_text),
            {},
            {},
            mode="case",
            turn_index=1,
        )

    spans = span_exporter.get_finished_spans()
    spans_by_name = {span.name: span for span in spans}
    assert spans_by_name["invoke_agent"].status.status_code == StatusCode.ERROR
    assert spans_by_name["execute_tool"].status.status_code == StatusCode.ERROR
    assert spans_by_name["execute_tool"].attributes["gen_ai.tool.name"] == "unknown"
    assert spans_by_name["execute_tool"].attributes["error.type"] == "RuntimeError"
    assert all(private_text not in str(dict(span.attributes)) for span in spans)


class _ToolGraph:
    def __init__(self, tool_name):
        self.tool_name = tool_name

    def invoke(self, graph_input, config):
        return tools.execute_tool(object(), self.tool_name, {})
