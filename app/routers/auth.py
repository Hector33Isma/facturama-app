from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import can_attempt_login, hash_password, record_login_attempt, verify_password
from app.core.session import clear_session
from app.core.db import get_session
from app.dependencies import csrf_protect, get_current_user, require_login
from app.models.user import User
from app.services.audit_service import log_action

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


def _login_context(request: Request, error: str | None = None):
    return {"request": request, "error": error, "csrf_token": request.state.session.get("csrf_token")}


@router.get("/login")
async def login_form(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", _login_context(request))


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
):
    client_ip = request.client.host if request.client else "unknown"
    attempt_key = f"{username}:{client_ip}"
    if not can_attempt_login(attempt_key):
        return templates.TemplateResponse(
            "login.html",
            _login_context(request, "Demasiados intentos. Intenta de nuevo en unos minutos."),
            status_code=429,
        )

    try:
        user = db.scalar(select(User).where(User.username == username))
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            record_login_attempt(attempt_key, False)
            log_action(
                db,
                user.id if user else None,
                "login_fail",
                {"username": username},
                client_ip,
                request.headers.get("user-agent"),
            )
            return templates.TemplateResponse(
                "login.html",
                _login_context(request, "Usuario o contraseña incorrectos o usuario inactivo."),
                status_code=400,
            )
    except ValueError as exc:
        record_login_attempt(attempt_key, False)
        return templates.TemplateResponse(
            "login.html",
            _login_context(request, f"Error de contraseña: {exc}"),
            status_code=400,
        )

    record_login_attempt(attempt_key, True)
    request.state.session["user_id"] = user.id
    request.state.session_changed = True
    user.last_login_at = datetime.utcnow()
    db.commit()
    log_action(db, user.id, "login_success", {"username": username}, client_ip, request.headers.get("user-agent"))
    resp = RedirectResponse(url="/", status_code=303)
    return resp


@router.post("/logout")
async def logout(request: Request, user=Depends(require_login), csrf=Depends(csrf_protect)):
    resp = RedirectResponse(url="/login", status_code=303)
    clear_session(resp)
    request.state.session = {}
    request.state.session_changed = False
    request.state.clear_session = True
    return resp
