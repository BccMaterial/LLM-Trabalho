from flask import Flask

from api.services.authentication_middleware import register_authentication_middleware


def test_undeclared_endpoint_requires_authentication():
    app = Flask(__name__)
    app.add_url_rule(
        "/api/undeclared",
        endpoint="undeclared_endpoint",
        view_func=lambda: "ok",
    )
    register_authentication_middleware(app)

    response = app.test_client().get("/api/undeclared")

    assert response.status_code == 401
