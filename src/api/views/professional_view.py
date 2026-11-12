from flask import jsonify

from ..models.professional import Professional
from ..services.pagination_service import PageResult


def professional_response(professional: Professional, status_code: int = 200):
    return jsonify(professional.to_dict()), status_code


def professionals_response(page: PageResult[Professional]):
    return jsonify(page.to_dict())


def error_response(message: str, status_code: int):
    return jsonify({"error": message}), status_code
