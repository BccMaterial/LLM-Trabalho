from datetime import datetime, timezone

from flask import jsonify

from ..models.professional import Professional
from ..services.pagination_service import PageResult


def professional_response(professional: Professional, status_code: int = 200):
    return jsonify(serialize_professional(professional)), status_code


def professionals_response(page: PageResult[Professional]):
    return jsonify(
        {
            "page": page.page,
            "page_size": page.page_size,
            "next_link": page.next_link,
            "value": [serialize_professional(item) for item in page.value],
            "total_items": page.total_items,
        }
    )


def error_response(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def serialize_professional(professional: Professional) -> dict[str, object]:
    return {
        "id": str(professional.id),
        "nome": professional.nome,
        "status": professional.status,
        "created_at": _timestamp(professional.created_at),
        "updated_at": _timestamp(professional.updated_at),
    }


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
