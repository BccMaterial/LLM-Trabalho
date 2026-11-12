from typing import TypedDict
from uuid import UUID

from sqlalchemy import Column, MetaData, String, Table, Uuid, inspect, select, update
from sqlalchemy.orm import Session

from ..models.professional import Professional
from .pagination_service import PageResult, PaginationParameters, PaginationService


class ProfessionalChanges(TypedDict, total=False):
    nome: str
    email: str
    cpf: str
    status: bool


class ProfessionalService:
    @staticmethod
    def create(
        session: Session,
        nome: str,
        email: str,
        cpf: str,
    ) -> Professional:
        professional = Professional(nome=nome, email=email, cpf=cpf)
        session.add(professional)
        session.flush()
        return professional

    @staticmethod
    def list(
        session: Session,
        parameters: PaginationParameters,
        request_url: str,
    ) -> PageResult[Professional]:
        statement = select(Professional).order_by(
            Professional.created_at,
            Professional.id,
        )
        return PaginationService.paginate(
            session,
            statement,
            parameters,
            request_url,
        )

    @staticmethod
    def get(session: Session, professional_id: UUID) -> Professional | None:
        return session.get(Professional, professional_id)

    @staticmethod
    def update(
        session: Session,
        professional: Professional,
        fields: ProfessionalChanges,
    ) -> Professional:
        if "nome" in fields:
            professional.nome = fields["nome"]
        if "email" in fields:
            professional.email = fields["email"]
        if "cpf" in fields:
            professional.cpf = fields["cpf"]

        if "status" in fields:
            professional.status = fields["status"]
            if not professional.status:
                ProfessionalService._cancel_appointments(
                    session,
                    professional.id,
                )

        session.flush()
        return professional

    @staticmethod
    def deactivate(session: Session, professional: Professional) -> Professional:
        professional.status = False
        ProfessionalService._cancel_appointments(session, professional.id)
        session.flush()
        return professional

    @staticmethod
    def _cancel_appointments(session: Session, professional_id: UUID) -> None:
        connection = session.connection()
        inspector = inspect(connection)
        if not inspector.has_table("appointments"):
            return

        columns = {column["name"] for column in inspector.get_columns("appointments")}
        missing_columns = {"id_profissional", "status"} - columns
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise RuntimeError(
                f"appointments table is missing required columns: {missing}"
            )

        appointments = Table(
            "appointments",
            MetaData(),
            Column("id_profissional", Uuid(as_uuid=True)),
            Column("status", String()),
            autoload_with=connection,
        )
        session.execute(
            update(appointments)
            .where(appointments.c.id_profissional == professional_id)
            .values(status="cancelado")
        )
