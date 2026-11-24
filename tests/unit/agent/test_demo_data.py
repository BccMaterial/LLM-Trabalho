import pytest

from src.agent import demo_data


def test_admin_request_rejects_remote_http_before_sending_token(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://api.example.test")
    monkeypatch.setenv("ADMIN_API_TOKEN", "admin-token")
    monkeypatch.setattr(
        demo_data,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("A requisição não deveria sair"),
    )

    with pytest.raises(RuntimeError, match="API_BASE_URL deve usar HTTPS"):
        demo_data._request("/api/users")


def test_populate_example_data_seeds_runtime_user_as_agent(monkeypatch):
    calls = []
    monkeypatch.setenv("API_USER", "agente.demo@example.test")
    monkeypatch.setenv("API_PASSWORD", "senha-agente")
    monkeypatch.setattr(
        demo_data,
        "_request",
        lambda path, method="GET", payload=None: calls.append((path, method, payload))
        or {},
    )
    monkeypatch.setattr(demo_data, "_find_user", lambda _email: {"id": "user-id"})
    monkeypatch.setattr(
        demo_data, "_find_professional", lambda _email: {"id": "prof-id"}
    )

    demo_data.populate_example_data()

    user_creation = next(call for call in calls if call[0] == "/api/users")
    user_update = next(call for call in calls if call[1] == "PATCH")
    assert user_creation[2]["type"] == "agent"
    assert user_update[2]["type"] == "agent"
