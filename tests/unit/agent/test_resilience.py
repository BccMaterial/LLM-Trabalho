import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest
from openai import APIConnectionError, APIStatusError, RateLimitError

from src.agent.integrations import api, llm
from src.agent.workflows.execution import (
    ErrorKind,
    ProviderTimeoutFailure,
    RateLimitFailure,
    classify_error_kind,
)


class FakeResponse:
    status_code = 200
    headers = {}
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class FakeOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def open(self, request, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, **_):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(
            model="fake-model",
            choices=[SimpleNamespace(finish_reason="stop")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=3),
        )


class FakeLlmClient:
    def __init__(self, outcomes):
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))

    def with_options(self, **_):
        return self


def _rate_limit():
    response = SimpleNamespace(
        status_code=429,
        headers={"retry-after": "1"},
        text="rate limited",
        request=SimpleNamespace(),
    )
    return RateLimitError("429", response=response, body=None)


def _client(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    monkeypatch.setattr(llm.random, "uniform", lambda *_: 0.0)
    return FakeLlmClient


def test_rate_limit_is_retried_and_succeeds(monkeypatch):
    client = _client(monkeypatch)([_rate_limit(), "ok"])

    response = llm._request_with_retry(client, [{}])

    assert response.model == "fake-model"
    assert client.chat.completions.outcomes == []


def test_daily_quota_exhaustion_is_not_retried(monkeypatch):
    error = _rate_limit()
    error.response.headers = {}
    client = _client(monkeypatch)([error])

    with pytest.raises(RateLimitFailure):
        llm._request_with_retry(client, [{}])

    assert client.chat.completions.calls == 1


def test_exhausted_rate_limit_has_structured_kind(monkeypatch):
    client = _client(monkeypatch)([_rate_limit() for _ in range(llm.MAX_LLM_RETRIES)])

    with pytest.raises(RateLimitFailure) as error:
        llm._request_with_retry(client, [{}])

    assert classify_error_kind(error.value) == ErrorKind.RATE_LIMIT


def test_connection_error_is_retried(monkeypatch):
    client = _client(monkeypatch)([APIConnectionError(request=SimpleNamespace()), "ok"])

    assert llm._request_with_retry(client, [{}]).model == "fake-model"


def test_permanent_http_error_is_not_retried(monkeypatch):
    response = SimpleNamespace(
        status_code=400, headers={}, text="bad request", request=SimpleNamespace()
    )
    error = APIStatusError("bad request", response=response, body=None)
    client = _client(monkeypatch)([error])

    with pytest.raises(RuntimeError, match="HTTP 400"):
        llm._request_with_retry(client, [{}])

    assert client.chat.completions.calls == 1


def test_llm_deadline_failure_has_timeout_kind(monkeypatch):
    client = _client(monkeypatch)([])

    with pytest.raises(ProviderTimeoutFailure):
        llm._request_with_retry(client, [{}], timeout_seconds=0)


def test_api_retries_idempotent_get_after_url_error(monkeypatch):
    opener = FakeOpener(
        [FakeResponse({}), URLError("transiente"), FakeResponse({"ok": True})]
    )
    monkeypatch.setattr(api, "build_opener", lambda: opener)
    monkeypatch.setattr(api.time, "sleep", lambda _: None)
    monkeypatch.setattr(api.random, "uniform", lambda *_: 0.0)
    monkeypatch.setenv("API_AGENT_USER", "agent@example.test")
    monkeypatch.setenv("API_AGENT_PASSWORD", "agent-secret")
    client = api.ApiClient()

    assert client._request("/api/test") == {"ok": True}
    assert opener.calls == 3  # login + falha + nova leitura


def test_api_does_not_retry_write_requests(monkeypatch):
    opener = FakeOpener([FakeResponse({}), URLError("transiente")])
    monkeypatch.setattr(api, "build_opener", lambda: opener)
    monkeypatch.setattr(api.time, "sleep", lambda _: None)
    monkeypatch.setenv("API_AGENT_USER", "agent@example.test")
    monkeypatch.setenv("API_AGENT_PASSWORD", "agent-secret")
    client = api.ApiClient()

    with pytest.raises(api.ApiUnavailableFailure):
        client._request("/api/appointments", method="POST", payload={})

    assert opener.calls == 2  # login + escrita única
