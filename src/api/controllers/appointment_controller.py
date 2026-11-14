from datetime import datetime
from uuid import UUID

from flask import Blueprint, current_app, g, request
from sqlalchemy.orm import Session

from ..models.appointment import Appointment
from ..policies.appointment_authorization_policy import AppointmentAuthorizationPolicy
from ..policies.authorization_context import current_actor_type
from ..services.appointment_service import (
    STATUSES,
    AppointmentChanges,
    AppointmentConflictError,
    AppointmentService,
    InvalidPatientError,
    InvalidProfessionalError,
)
from ..services.pagination_service import InvalidPageError, PaginationParameters
from ..utils.validators import json_object, parse_uuid
from ..views import appointment_view, error_view

appointment_controller = Blueprint("appointment_controller", __name__)


@appointment_controller.post("/api/appointments")
def create_appointment():
    if not AppointmentAuthorizationPolicy.can_write(current_actor_type()):
        return _permission_denied()
    fields = _parse_fields(json_object(), partial=False)
    if fields is None:
        return _invalid_data()

    def create(session: Session):
        return AppointmentService.create(session, **fields)

    try:
        appointment = current_app.extensions["database_service"].run_with_session(
            create
        )
    except InvalidPatientError:
        return _invalid_data("The patient_id must identify a patient user.")
    except InvalidProfessionalError:
        return _invalid_data("The professional_id must identify a professional.")
    except AppointmentConflictError:
        return _conflict()
    except ValueError:
        return _invalid_data("agenda_inicio must be before agenda_fim.")
    return appointment_view.appointment_response(appointment, 201)


@appointment_controller.get("/api/appointments")
def list_appointments():
    actor_type = current_actor_type()
    if not AppointmentAuthorizationPolicy.can_read_all(
        actor_type
    ) and not AppointmentAuthorizationPolicy.can_read_own(actor_type):
        return _permission_denied()
    requested_patient = _query_uuid("patient_id")
    professional_id = _query_uuid("professional_id")
    if request.args.get("patient_id") and requested_patient is None:
        return _invalid_data("patient_id must be a UUID.")
    if request.args.get("professional_id") and professional_id is None:
        return _invalid_data("professional_id must be a UUID.")
    actor = getattr(g, "authenticated_user", None)
    if actor_type == "patient":
        if requested_patient is not None and requested_patient != actor.id:
            return _permission_denied()
        requested_patient = actor.id
    try:
        parameters = PaginationParameters.from_query_params(request.args)
    except InvalidPageError:
        return error_view.error_response(
            "Invalid page parameter", 400, "Use an integer greater than or equal to 1."
        )
    page = current_app.extensions["database_service"].run_with_session(
        AppointmentService.list,
        parameters,
        request.url,
        requested_patient,
        professional_id,
    )
    return appointment_view.appointments_response(page)


@appointment_controller.patch("/api/appointments/<appointment_id>")
def update_appointment(appointment_id: str):
    if not AppointmentAuthorizationPolicy.can_write(current_actor_type()):
        return _permission_denied()
    parsed_id = parse_uuid(appointment_id)
    fields = _parse_fields(json_object(), partial=True)
    if parsed_id is None:
        return _not_found()
    if fields is None:
        return _invalid_data()

    def update(session: Session):
        appointment = AppointmentService.get(session, parsed_id)
        return (
            None
            if appointment is None
            else AppointmentService.update(session, appointment, fields)
        )

    try:
        appointment = current_app.extensions["database_service"].run_with_session(
            update
        )
    except InvalidPatientError:
        return _invalid_data("The patient_id must identify a patient user.")
    except InvalidProfessionalError:
        return _invalid_data("The professional_id must identify a professional.")
    except AppointmentConflictError:
        return _conflict()
    except ValueError:
        return _invalid_data("agenda_inicio must be before agenda_fim.")
    if appointment is None:
        return _not_found()
    return appointment_view.appointment_response(appointment)


@appointment_controller.delete("/api/appointments/<appointment_id>")
def cancel_appointment(appointment_id: str):
    if not AppointmentAuthorizationPolicy.can_write(current_actor_type()):
        return _permission_denied()
    parsed_id = parse_uuid(appointment_id)
    if parsed_id is None:
        return _not_found()

    def cancel(session: Session):
        appointment = AppointmentService.get(session, parsed_id)
        return (
            None
            if appointment is None
            else AppointmentService.cancel(session, appointment)
        )

    appointment = current_app.extensions["database_service"].run_with_session(cancel)
    return (
        _not_found()
        if appointment is None
        else appointment_view.appointment_response(appointment)
    )


def _parse_fields(payload, partial):
    if payload is None:
        return None
    allowed = {
        "patient_id",
        "id_paciente",
        "professional_id",
        "id_profissional",
        "agenda_inicio",
        "agenda_fim",
        "start",
        "end",
        "suspeita_paciente",
        "status",
    }
    if not partial and not {"patient_id", "id_paciente"} & payload.keys():
        return None
    if set(payload) - allowed or (partial and not payload):
        return None
    fields = {}
    for canonical, aliases in {
        "patient_id": ("patient_id", "id_paciente"),
        "professional_id": ("professional_id", "id_profissional"),
    }.items():
        present = next((key for key in aliases if key in payload), None)
        if present is not None:
            value = (
                parse_uuid(payload[present])
                if isinstance(payload[present], str)
                else None
            )
            if value is None:
                return None
            fields[canonical] = value
    for canonical, aliases in {
        "agenda_inicio": ("agenda_inicio", "start"),
        "agenda_fim": ("agenda_fim", "end"),
    }.items():
        present = next((key for key in aliases if key in payload), None)
        if present is not None:
            value = _parse_datetime(payload[present])
            if value is None:
                return None
            fields[canonical] = value
    if not partial and not all(
        any(alias in payload for alias in aliases)
        for aliases in (
            ("professional_id", "id_profissional"),
            ("agenda_inicio", "start"),
            ("agenda_fim", "end"),
            ("suspeita_paciente",),
        )
    ):
        return None
    if "suspeita_paciente" in payload:
        if (
            not isinstance(payload["suspeita_paciente"], str)
            or not payload["suspeita_paciente"].strip()
        ):
            return None
        fields["suspeita_paciente"] = payload["suspeita_paciente"].strip()
    if "status" in payload:
        if not isinstance(payload["status"], str) or payload["status"] not in STATUSES:
            return None
        fields["status"] = payload["status"]
    if not partial and "status" not in fields:
        fields["status"] = "Pendente"
    return fields


def _parse_datetime(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _query_uuid(name: str) -> UUID | None:
    value = request.args.get(name)
    return parse_uuid(value) if value is not None else None


def _invalid_data(
    action="Provide valid patient, professional, time, suspicion, and status values.",
):
    return error_view.error_response("Invalid appointment data", 400, action)


def _conflict():
    return error_view.error_response(
        "Appointment conflict",
        409,
        "The professional already has a pending appointment in this interval.",
    )


def _not_found():
    return error_view.error_response(
        "Appointment not found", 404, "Verify the appointment ID and try again."
    )


def _permission_denied():
    return error_view.error_response(
        "Permission denied",
        403,
        "Your account is not authorized to perform this action.",
    )
