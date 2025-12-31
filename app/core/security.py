import time
from typing import Dict, List

from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_login_attempts: Dict[str, List[float]] = {}


def validate_password_length(password: str) -> None:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no debe exceder 72 bytes (límite bcrypt).")


def verify_password(plain_password: str, password_hash: str) -> bool:
    validate_password_length(plain_password)
    return pwd_context.verify(plain_password, password_hash)


def hash_password(password: str) -> str:
    validate_password_length(password)
    return pwd_context.hash(password)


def can_attempt_login(key: str) -> bool:
    now = time.time()
    window = settings.login_rate_limit_window
    limit = settings.login_rate_limit_count
    attempts = _login_attempts.get(key, [])
    attempts = [ts for ts in attempts if now - ts <= window]
    _login_attempts[key] = attempts
    return len(attempts) < limit


def record_login_attempt(key: str, success: bool) -> None:
    now = time.time()
    attempts = _login_attempts.get(key, [])
    if not success:
        attempts.append(now)
        _login_attempts[key] = attempts
    else:
        _login_attempts[key] = []
