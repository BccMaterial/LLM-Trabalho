from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from flask import Blueprint, current_app, request
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest

from ..models.professional import Professional
from ..services.pagination_service import InvalidPageError, PaginationParameters
from ..services.professional_service import (
    ProfessionalChanges,
    ProfessionalService,
)
from ..views import error_view, professional_view

professional_controller = Blueprint("professional_controller", __name__)
Result = TypeVar("Result")


@professional_controller.post("/api/professionals")
def create_professional():
    payload = _json_object()
    nome = _validated_create_name(payload)
    if nome is None:
        return error_view.error_response(
            "Invalid professional data",
            400,
            "Provide a non-empty name of at most 255 characters.",
        )

    professional = _run_with_session(ProfessionalService.create, nome)
    return professional_view.professional_response(professional, 201)


@professional_controller.get("/api/professionals")
def list_professionals():
    try:
        parameters = PaginationParameters.from_query_params(request.args)
    except InvalidPageError:
        return error_view.error_response(
            "Invalid page parameter",
            400,
            "Use an integer greater than or equal to 1.",
        )

    page = _run_with_session(ProfessionalService.list, parameters, request.url)
    return professional_view.professionals_response(page)


@professional_controller.get("/api/professionals/<professional_id>")
def get_professional(professional_id: str):
    parsed_id = _parse_id(professional_id)
    if parsed_id is None:
        return _professional_not_found()

    professional = _run_with_session(ProfessionalService.get, parsed_id)
    if professional is None:
        return _professional_not_found()
    return professional_view.professional_response(professional)


@professional_controller.patch("/api/professionals/<professional_id>")
def update_professional(professional_id: str):
    parsed_id = _parse_id(professional_id)
    if parsed_id is None:
        return _professional_not_found()

    payload = _json_object()
    fields = _validated_patch_fields(payload)
    if fields is None:
        return error_view.error_response(
            "Invalid professional data",
            400,
            "Provide a non-empty name of at most 255 characters and a boolean status.",
        )

    def update(session: Session) -> Professional | None:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return None
        return ProfessionalService.update(session, professional, fields)

    updated = _run_with_session(update)
    if updated is None:
        return _professional_not_found()
    return professional_view.professional_response(updated)


@professional_controller.delete("/api/professionals/<professional_id>")
def deactivate_professional(professional_id: str):
    parsed_id = _parse_id(professional_id)
    if parsed_id is None:
        return _professional_not_found()

    def deactivate(session: Session) -> Professional | None:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return None
        return ProfessionalService.deactivate(session, professional)

    deactivated = _run_with_session(deactivate)
    if deactivated is None:
        return _professional_not_found()
    return professional_view.professional_response(deactivated)


def _run_with_session(operation: Callable[..., Result], *args: object) -> Result:
    return current_app.extensions["database_service"].run_with_session(operation, *args)


def _professional_not_found():
    return error_view.error_response(
        "Professional not found",
        404,
        "Verify the professional ID and try again.",
    )


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
