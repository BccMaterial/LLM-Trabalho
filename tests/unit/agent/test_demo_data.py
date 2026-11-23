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
