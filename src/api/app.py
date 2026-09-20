import os

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/api/example")
def example():
    """Return a small JSON response that can be exposed as an agent tool."""
    name = request.args.get("name", "mundo")
    return jsonify(
        {
            "message": f"Olá, {name}!",
            "success": True,
        }
    )


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
