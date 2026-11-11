from flask import jsonify


def example_response(name: str):
    return jsonify(
        {
            "message": f"Olá, {name}!",
            "success": True,
        }
    )
