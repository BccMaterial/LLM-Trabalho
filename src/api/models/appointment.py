from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    patient_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    professional_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("professionals.id"), nullable=False
    )
    agenda_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    agenda_fim: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    suspeita_paciente: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Pendente")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "professional_id": str(self.professional_id),
            "id_paciente": str(self.patient_id),
            "id_profissional": str(self.professional_id),
            "agenda_inicio": _timestamp(self.agenda_inicio),
            "agenda_fim": _timestamp(self.agenda_fim),
            "suspeita_paciente": self.suspeita_paciente,
            "status": self.status,
            "created_at": _timestamp(self.created_at),
            "updated_at": _timestamp(self.updated_at),
        }


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
