from flask import jsonify

from ..models.professional import Professional
from ..services.pagination_service import PageResult


def professional_response(professional: Professional, status_code: int = 200):
    return jsonify(professional.to_dict()), status_code


def professionals_response(page: PageResult[Professional]):
    return jsonify(page.to_dict())


def active_professionals_response(page: PageResult[Professional]):
    return jsonify(
        {
            "page": page.page,
            "page_size": page.page_size,
            "next_link": page.next_link,
            "value": [{"id": str(item.id), "nome": item.nome} for item in page.value],
            "total_items": page.total_items,
        }
    )
