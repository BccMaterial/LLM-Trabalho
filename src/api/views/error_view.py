from flask import jsonify


def error_response(
    error: str,
    status_code: int,
    action: str | None = None,
):
    payload: dict[str, str | int] = {
        "error": error,
        "status_code": status_code,
    }
    if action is not None:
        payload["action"] = action
    return jsonify(payload), status_code
