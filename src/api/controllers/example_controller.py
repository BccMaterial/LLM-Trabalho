from flask import Blueprint, request

from ..views.example_view import example_response

example_controller = Blueprint("example_controller", __name__)


@example_controller.get("/api/example")
def example():
    name = request.args.get("name", "mundo")
    return example_response(name)
