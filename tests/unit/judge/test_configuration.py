import pytest

from src.judge import client, run_suite


def test_judge_client_uses_only_judge_environment(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("JUDGE_LLM_BASE_URL", "https://juiz.example.test/v1")
    monkeypatch.setenv("JUDGE_LLM_API_KEY", "chave-do-juiz")
    monkeypatch.setenv("JUDGE_LLM_MODEL", "juiz-modelo")
    monkeypatch.setenv("OPENAI_API_KEY", "chave-antiga-do-agente")
    monkeypatch.setattr(client, "OpenAI", FakeOpenAI)

    client.create_client()
    assert captured["base_url"] == "https://juiz.example.test/v1"
    assert captured["api_key"] == "chave-do-juiz"


def test_judge_client_rejects_old_variable_name(monkeypatch):
    monkeypatch.setattr(client, "load_dotenv", lambda *_: None)
    for name in ("JUDGE_LLM_BASE_URL", "JUDGE_LLM_API_KEY", "JUDGE_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "chave-antiga")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY foi renomeada"):
        client.create_client()


def test_judge_client_rejects_remote_http(monkeypatch):
    monkeypatch.setenv("JUDGE_LLM_BASE_URL", "http://judge.example.test/v1")
    monkeypatch.setenv("JUDGE_LLM_API_KEY", "judge-key")
    monkeypatch.setenv("JUDGE_LLM_MODEL", "judge-model")

    with pytest.raises(RuntimeError, match="deve usar HTTPS"):
        client.create_client()


def test_run_identity_records_agent_prompt_and_separate_models(monkeypatch):
    for name, value in {
        "LLM_BASE_URL": "https://agente.example.test/v1",
        "LLM_API_KEY": "chave-do-agente",
        "LLM_MODEL": "modelo-do-agente",
        "JUDGE_LLM_BASE_URL": "https://juiz.example.test/v1",
        "JUDGE_LLM_API_KEY": "chave-do-juiz",
        "JUDGE_LLM_MODEL": "modelo-do-juiz",
    }.items():
        monkeypatch.setenv(name, value)

    identity = run_suite._identity("v1", "mudança", judge_enabled=True)
    assert identity["agent_model"] == "modelo-do-agente"
    assert identity["judge"]["model"] == "modelo-do-juiz"
    assert len(identity["agent_prompt_sha256"]) == 64
    assert len(identity["dataset_sha256"]) == 64
    assert identity["version"] == "v1"
    assert identity["change"] == "mudança"


def test_synthetic_trace_payload_capture_rejects_production_cases():
    with pytest.raises(ValueError, match="só é permitida"):
        run_suite._validate_synthetic_payload_capture(
            [{"id": "prod-01", "origem": "producao"}]
        )

    run_suite._validate_synthetic_payload_capture(
        [
            {"id": "dev-01", "origem": "desenvolvimento"},
            {"id": "syn-01", "origem": "sintetico"},
        ]
    )
