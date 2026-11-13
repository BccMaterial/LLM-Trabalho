import hashlib
import hmac

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError


class PasswordPepperNotConfiguredError(RuntimeError):
    pass


_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str, pepper: str | None) -> str:
    return _password_hasher.hash(_peppered_password(password, pepper))


def verify_password(password: str, password_hash: str, pepper: str | None) -> bool:
    try:
        return _password_hasher.verify(
            password_hash,
            _peppered_password(password, pepper),
        )
    except VerifyMismatchError:
        return False


def _peppered_password(password: str, pepper: str | None) -> str:
    if not pepper:
        raise PasswordPepperNotConfiguredError(
            "PASSWORD_PEPPER must be configured to hash or verify passwords"
        )
    return hmac.new(
        pepper.encode(),
        password.encode(),
        hashlib.sha256,
    ).hexdigest()
