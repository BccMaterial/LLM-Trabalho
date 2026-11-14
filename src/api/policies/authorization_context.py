from flask import g


def current_actor_type() -> str | None:
    if getattr(g, "admin_api_token", False):
        return "admin"
    user = getattr(g, "authenticated_user", None)
    return user.type if user is not None else None
