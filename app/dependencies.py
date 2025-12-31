from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models.user import User


async def get_current_user(request: Request, db: Session = Depends(get_session)) -> User | None:
    user_id = request.state.session.get("user_id") if hasattr(request.state, "session") else None
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    request.state.user = user
    return user


async def require_login(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


async def require_admin(user: User = Depends(require_login)):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin requerido")
    return user


async def csrf_protect(request: Request):
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    session_token = getattr(request.state, "session", {}).get("csrf_token")
    form_token = None
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded") or request.headers.get(
        "content-type", ""
    ).startswith("multipart/form-data"):
        form_token = (await request.form()).get("csrf_token")
    else:
        form_token = request.headers.get("X-CSRF-Token")
    if not session_token or not form_token or form_token != session_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSRF token inválido")
