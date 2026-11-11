from uuid import UUID

from flask import Blueprint, current_app, request
from werkzeug.exceptions import BadRequest

from ..services.pagination_service import InvalidPageError, PaginationParameters
from ..services.professional_service import (
    ProfessionalChanges,
    ProfessionalService,
)
from ..views import professional_view

professional_controller = Blueprint("professional_controller", __name__)


@professional_controller.post("/api/professionals")
def create_professional():
    payload = _json_object()
    nome = _validated_create_name(payload)
    if nome is None:
        return professional_view.error_response("Invalid professional data", 400)

    with current_app.extensions["database_connector"].session() as session:
        professional = ProfessionalService.create(session, nome)
        return professional_view.professional_response(professional, 201)


@professional_controller.get("/api/professionals")
def list_professionals():
    try:
        parameters = PaginationParameters.from_query_params(request.args)
    except InvalidPageError:
        return professional_view.error_response("Invalid page parameter", 400)

    with current_app.extensions["database_connector"].session() as session:
        page = ProfessionalService.list(session, parameters, request.url)
        return professional_view.professionals_response(page)


@professional_controller.get("/api/professionals/<professional_id>")
def get_professional(professional_id: str):
    parsed_id = _parse_id(professional_id)
    if parsed_id is None:
        return professional_view.error_response("Professional not found", 404)

    with current_app.extensions["database_connector"].session() as session:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return professional_view.error_response("Professional not found", 404)
        return professional_view.professional_response(professional)


@professional_controller.patch("/api/professionals/<professional_id>")
def update_professional(professional_id: str):
    parsed_id = _parse_id(professional_id)
    if parsed_id is None:
        return professional_view.error_response("Professional not found", 404)

    payload = _json_object()
    fields = _validated_patch_fields(payload)
    if fields is None:
        return professional_view.error_response("Invalid professional data", 400)

    with current_app.extensions["database_connector"].session() as session:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return professional_view.error_response("Professional not found", 404)
        updated = ProfessionalService.update(session, professional, fields)
        return professional_view.professional_response(updated)


@professional_controller.delete("/api/professionals/<professional_id>")
def deactivate_professional(professional_id: str):
    parsed_id = _parse_id(professional_id)
    if parsed_id is None:
        return professional_view.error_response("Professional not found", 404)

    with current_app.extensions["database_connector"].session() as session:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return professional_view.error_response("Professional not found", 404)
        deactivated = ProfessionalService.deactivate(session, professional)
        return professional_view.professional_response(deactivated)


def _json_object() -> dict[str, object] | None:
    if not request.is_json:
        return None
    try:
        payload = request.get_json()
    except BadRequest:
        return None
    return payload if isinstance(payload, dict) else None


def _validated_create_name(payload: dict[str, object] | None) -> str | None:
    if payload is None:
        return None
    if set(payload) - {"nome", "status"}:
        return None
    nome = payload.get("nome")
    status = payload.get("status", True)
    if (
        not isinstance(nome, str)
        or not nome.strip()
        or len(nome.strip()) > 255
        or type(status) is not bool
        or not status
    ):
        return None
    return nome.strip()


def _validated_patch_fields(
    payload: dict[str, object] | None,
) -> ProfessionalChanges | None:
    if payload is None or not payload or set(payload) - {"nome", "status"}:
        return None

    fields: ProfessionalChanges = {}
    if "nome" in payload:
        nome = payload["nome"]
        if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > 255:
            return None
        fields["nome"] = nome.strip()
    if "status" in payload:
        status = payload["status"]
        if type(status) is not bool:
            return None
        fields["status"] = status
    return fields


def _parse_id(professional_id: str) -> UUID | None:
    try:
        return UUID(professional_id)
    except ValueError:
        return None
