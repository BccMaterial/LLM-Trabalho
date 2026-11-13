from flask import jsonify

from ..models.user import User
from ..services.pagination_service import PageResult


def user_response(user: User, status_code: int = 200):
    return jsonify(user.to_dict()), status_code


def users_response(page: PageResult[User]):
    return jsonify(page.to_dict())
