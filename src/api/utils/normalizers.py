import re


def normalize_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return None
    return email


def normalize_username(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    username = value.strip()
    if not username or len(username) > 100:
        return None
    return username
