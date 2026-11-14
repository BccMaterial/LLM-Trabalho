from flask import jsonify

from ..models.appointment import Appointment
from ..services.pagination_service import PageResult


def appointment_response(appointment: Appointment, status_code: int = 200):
    return jsonify(appointment.to_dict()), status_code


def appointments_response(page: PageResult[Appointment]):
    return jsonify(page.to_dict())
