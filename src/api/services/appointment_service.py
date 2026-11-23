from datetime import datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models.appointment import Appointment
from ..models.professional import Professional
from ..models.user import User
from .pagination_service import PageResult, PaginationParameters, PaginationService

STATUSES = frozenset({"Falta", "Pendente", "Concluído", "Cancelado"})


class AppointmentChanges(TypedDict, total=False):
    patient_id: UUID
    professional_id: UUID
    agenda_inicio: datetime
    agenda_fim: datetime
    suspeita_paciente: str
    status: str


class AppointmentConflictError(Exception):
    pass


class InvalidPatientError(Exception):
    pass


class InvalidProfessionalError(Exception):
    pass


class AppointmentService:
    @staticmethod
    def create(session: Session, **fields: object) -> Appointment:
        patient = session.get(User, fields["patient_id"])
        if patient is None or patient.type != "patient":
            raise InvalidPatientError
        if session.get(Professional, fields["professional_id"]) is None:
            raise InvalidProfessionalError
        if fields["agenda_inicio"] >= fields["agenda_fim"]:
            raise ValueError
        if fields.get(
            "status", "Pendente"
        ) == "Pendente" and AppointmentService._has_conflict(
            session,
            fields["professional_id"],
            fields["patient_id"],
            fields["agenda_inicio"],
            fields["agenda_fim"],
        ):
            raise AppointmentConflictError
        appointment = Appointment(**fields)
        session.add(appointment)
        session.flush()
        return appointment

    @staticmethod
    def list(
        session: Session,
        parameters: PaginationParameters,
        request_url: str,
        patient_id: UUID | None = None,
        professional_id: UUID | None = None,
    ) -> PageResult[Appointment]:
        statement = select(Appointment).order_by(
            Appointment.agenda_inicio, Appointment.id
        )
        if patient_id is not None:
            statement = statement.where(Appointment.patient_id == patient_id)
        if professional_id is not None:
            statement = statement.where(Appointment.professional_id == professional_id)
        return PaginationService.paginate(session, statement, parameters, request_url)

    @staticmethod
    def is_professional_available(
        session: Session,
        professional_id: UUID,
        start: datetime,
        end: datetime,
    ) -> bool:
        statement = (
            select(Appointment.id)
            .where(
                Appointment.professional_id == professional_id,
                Appointment.status == "Pendente",
                Appointment.agenda_inicio < end,
                Appointment.agenda_fim > start,
            )
            .limit(1)
        )
        return session.scalar(statement) is None

    @staticmethod
    def get(session: Session, appointment_id: UUID) -> Appointment | None:
        return session.get(Appointment, appointment_id)

    @staticmethod
    def update(session: Session, appointment: Appointment, fields: AppointmentChanges):
        merged = {
            "patient_id": fields.get("patient_id", appointment.patient_id),
            "professional_id": fields.get(
                "professional_id", appointment.professional_id
            ),
            "agenda_inicio": fields.get("agenda_inicio", appointment.agenda_inicio),
            "agenda_fim": fields.get("agenda_fim", appointment.agenda_fim),
        }
        if "patient_id" in fields:
            patient = session.get(User, fields["patient_id"])
            if patient is None or patient.type != "patient":
                raise InvalidPatientError
        if (
            "professional_id" in fields
            and session.get(Professional, fields["professional_id"]) is None
        ):
            raise InvalidProfessionalError
        if merged["agenda_inicio"] >= merged["agenda_fim"]:
            raise ValueError
        if fields.get(
            "status", appointment.status
        ) == "Pendente" and AppointmentService._has_conflict(
            session,
            merged["professional_id"],
            merged["patient_id"],
            merged["agenda_inicio"],
            merged["agenda_fim"],
            appointment.id,
        ):
            raise AppointmentConflictError
        for field, value in fields.items():
            setattr(appointment, field, value)
        session.flush()
        return appointment

    @staticmethod
    def cancel(session: Session, appointment: Appointment) -> Appointment:
        appointment.status = "Cancelado"
        session.flush()
        return appointment

    @staticmethod
    def _has_conflict(
        session,
        professional_id,
        patient_id,
        start,
        end,
        exclude_id=None,
    ):
        query = select(Appointment.id).where(
            Appointment.status == "Pendente",
            or_(
                Appointment.professional_id == professional_id,
                Appointment.patient_id == patient_id,
            ),
            and_(Appointment.agenda_inicio < end, Appointment.agenda_fim > start),
        )
        if exclude_id is not None:
            query = query.where(Appointment.id != exclude_id)
        return session.scalar(query) is not None
