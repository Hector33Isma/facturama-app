import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

from itsdangerous import BadSignature, URLSafeSerializer
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

serializer = URLSafeSerializer(settings.secret_key, salt="session")


def load_session(request: Request) -> Dict:
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return {}
    try:
        data = serializer.loads(cookie)
        if isinstance(data, dict):
            return data
    except BadSignature:
        return {}
    return {}


def save_session(response: Response, session_data: Dict) -> None:
    token = serializer.dumps(session_data)
    max_age = settings.session_max_age_seconds
    expires = datetime.now(timezone.utc) + timedelta(seconds=max_age)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() == "production",
        max_age=max_age,
        expires=expires,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name)


def ensure_csrf(session_data: Dict) -> tuple[str, bool]:
    created = False
    if "csrf_token" not in session_data:
        session_data["csrf_token"] = secrets.token_hex(16)
        created = True
    return session_data["csrf_token"], created


def ensure_session_exp(session_data: Dict) -> bool:
    """Set or refresh session expiration timestamp. Returns True if modified."""
    exp = time.time() + settings.session_max_age_seconds
    session_data["exp"] = exp
    return True


def is_session_expired(session_data: Dict) -> bool:
    exp = session_data.get("exp")
    if not exp:
        return False
    try:
        return float(exp) < time.time()
    except (TypeError, ValueError):
        return True
