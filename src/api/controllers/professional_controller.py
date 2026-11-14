from flask import Blueprint, current_app, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.professional import Professional
from ..services.pagination_service import InvalidPageError, PaginationParameters
from ..services.professional_service import (
    ProfessionalChanges,
    ProfessionalService,
)
from ..utils.normalizers import normalize_email
from ..utils.validators import (
    is_identity_conflict,
    is_valid_cpf,
    json_object,
    parse_uuid,
)
from ..views import error_view, professional_view

professional_controller = Blueprint("professional_controller", __name__)


@professional_controller.post("/api/professionals")
def create_professional():
    db_service = current_app.extensions["database_service"]
    payload = json_object()
    fields = _validated_create_fields(payload)
    if fields is None:
        return error_view.error_response(
            "Invalid professional data",
            400,
            "Provide a name, a valid email address, and an unmasked 11-digit CPF.",
        )

    try:
        professional = db_service.run_with_session(
            ProfessionalService.create,
            fields["nome"],
            fields["email"],
            fields["cpf"],
        )
    except IntegrityError as error:
        if not is_identity_conflict(
            error,
            {"uq_professionals_email", "uq_professionals_cpf"},
            "professionals",
        ):
            raise
        return _identity_conflict()
    return professional_view.professional_response(professional, 201)


@professional_controller.get("/api/professionals")
def list_professionals():
    db_service = current_app.extensions["database_service"]
    try:
        parameters = PaginationParameters.from_query_params(request.args)
    except InvalidPageError:
        return error_view.error_response(
            "Invalid page parameter",
            400,
            "Use an integer greater than or equal to 1.",
        )

    page = db_service.run_with_session(
        ProfessionalService.list, parameters, request.url
    )
    return professional_view.professionals_response(page)


@professional_controller.get("/api/professionals/<professional_id>")
def get_professional(professional_id: str):
    db_service = current_app.extensions["database_service"]
    parsed_id = parse_uuid(professional_id)
    if parsed_id is None:
        return _professional_not_found()

    professional = db_service.run_with_session(ProfessionalService.get, parsed_id)
    if professional is None:
        return _professional_not_found()
    return professional_view.professional_response(professional)


@professional_controller.patch("/api/professionals/<professional_id>")
def update_professional(professional_id: str):
    db_service = current_app.extensions["database_service"]
    parsed_id = parse_uuid(professional_id)
    if parsed_id is None:
        return _professional_not_found()

    payload = json_object()
    fields = _validated_patch_fields(payload)
    if fields is None:
        return error_view.error_response(
            "Invalid professional data",
            400,
            "Provide valid values for the supplied name, email, CPF, and status.",
        )

    def update(session: Session) -> Professional | None:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return None
        return ProfessionalService.update(session, professional, fields)

    try:
        updated = db_service.run_with_session(update)
    except IntegrityError as error:
        if not is_identity_conflict(
            error,
            {"uq_professionals_email", "uq_professionals_cpf"},
            "professionals",
        ):
            raise
        return _identity_conflict()
    if updated is None:
        return _professional_not_found()
    return professional_view.professional_response(updated)


@professional_controller.delete("/api/professionals/<professional_id>")
def deactivate_professional(professional_id: str):
    db_service = current_app.extensions["database_service"]
    parsed_id = parse_uuid(professional_id)
    if parsed_id is None:
        return _professional_not_found()

    def deactivate(session: Session) -> Professional | None:
        professional = ProfessionalService.get(session, parsed_id)
        if professional is None:
            return None
        return ProfessionalService.deactivate(session, professional)

    deactivated = db_service.run_with_session(deactivate)
    if deactivated is None:
        return _professional_not_found()
    return professional_view.professional_response(deactivated)


def _professional_not_found():
    return error_view.error_response(
        "Professional not found",
        404,
        "Verify the professional ID and try again.",
    )


def _validated_create_fields(
    payload: dict[str, object] | None,
) -> dict[str, str] | None:
    if payload is None:
        return None
    if set(payload) - {"nome", "email", "cpf", "status"}:
        return None
    nome = payload.get("nome")
    email = normalize_email(payload.get("email"))
    cpf = payload.get("cpf")
    status = payload.get("status", True)
    if (
        not isinstance(nome, str)
        or not nome.strip()
        or len(nome.strip()) > 255
        or email is None
        or not is_valid_cpf(cpf)
        or type(status) is not bool
        or not status
    ):
        return None
    return {"nome": nome.strip(), "email": email, "cpf": cpf}


def _validated_patch_fields(
    payload: dict[str, object] | None,
) -> ProfessionalChanges | None:
    if (
        payload is None
        or not payload
        or set(payload) - {"nome", "email", "cpf", "status"}
    ):
        return None

    fields: ProfessionalChanges = {}
    if "nome" in payload:
        nome = payload["nome"]
        if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > 255:
            return None
        fields["nome"] = nome.strip()
    if "email" in payload:
        email = normalize_email(payload["email"])
        if email is None:
            return None
        fields["email"] = email
    if "cpf" in payload:
        cpf = payload["cpf"]
        if not is_valid_cpf(cpf):
            return None
        fields["cpf"] = cpf
    if "status" in payload:
        status = payload["status"]
        if type(status) is not bool:
            return None
        fields["status"] = status
    return fields


def _identity_conflict():
    return error_view.error_response(
        "Professional email or CPF already exists",
        409,
        "Use an email and CPF not assigned to another professional.",
    )
