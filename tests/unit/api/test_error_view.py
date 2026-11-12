from flask import Flask

from api.views.error_view import error_response


def test_error_response_includes_error_status_and_optional_action():
    app = Flask(__name__)

    with app.app_context():
        response, status_code = error_response(
            "Invalid input",
            400,
            "Correct the input and retry.",
        )
        response_without_action, second_status_code = error_response(
            "Not found",
            404,
        )

    assert status_code == 400
    assert response.get_json() == {
        "error": "Invalid input",
        "status_code": 400,
        "action": "Correct the input and retry.",
    }
    assert second_status_code == 404
    assert response_without_action.get_json() == {
        "error": "Not found",
        "status_code": 404,
    }
