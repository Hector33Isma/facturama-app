from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.db import get_session
from app.dependencies import csrf_protect, require_admin
from app.models.user import User
from app.services.audit_service import log_action

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/users", dependencies=[Depends(require_admin)])


def _base_context(request: Request):
    return {"request": request, "csrf_token": request.state.session.get("csrf_token"), "user": getattr(request.state, "user", None)}


@router.get("")
async def list_users(request: Request, db: Session = Depends(get_session)):
    users = db.scalars(select(User).order_by(User.id)).all()
    return templates.TemplateResponse("users.html", {**_base_context(request), "users": users})


@router.get("/new")
async def new_user_form(request: Request):
    return templates.TemplateResponse(
        "user_form.html", {**_base_context(request), "user_obj": None, "action": "create", "error": None}
    )


@router.post("/new")
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(""),
    role: str = Form("user"),
    password: str = Form(...),
    db: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
):
    if db.scalar(select(User).where(User.username == username)):
        return templates.TemplateResponse(
            "user_form.html",
            {**_base_context(request), "user_obj": None, "action": "create", "error": "Usuario ya existe"},
            status_code=400,
        )
    try:
        pwd_hash = hash_password(password)
    except ValueError as exc:
        return templates.TemplateResponse(
            "user_form.html",
            {**_base_context(request), "user_obj": None, "action": "create", "error": str(exc)},
            status_code=400,
        )
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        is_active=True,
        password_hash=pwd_hash,
    )
    db.add(user)
    db.commit()
    log_action(db, getattr(request.state, "user", None).id if getattr(request.state, "user", None) else None, "create_user", {"username": username}, request.client.host if request.client else None, request.headers.get("user-agent"))
    return RedirectResponse(url="/users", status_code=303)


@router.get("/{user_id}/edit")
async def edit_user_form(user_id: int, request: Request, db: Session = Depends(get_session)):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse(url="/users", status_code=303)
    return templates.TemplateResponse(
        "user_form.html", {**_base_context(request), "user_obj": user_obj, "action": "edit", "error": None}
    )


@router.post("/{user_id}/edit")
async def edit_user(
    user_id: int,
    request: Request,
    email: str = Form(...),
    full_name: str = Form(""),
    role: str = Form("user"),
    is_active: bool | None = Form(False),
    db: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse(url="/users", status_code=303)
    user_obj.email = email
    user_obj.full_name = full_name
    user_obj.role = role
    user_obj.is_active = bool(is_active)
    db.commit()
    log_action(db, getattr(request.state, "user", None).id if getattr(request.state, "user", None) else None, "update_user", {"user_id": user_id}, request.client.host if request.client else None, request.headers.get("user-agent"))
    return RedirectResponse(url="/users", status_code=303)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse(url="/users", status_code=303)
    try:
        user_obj.password_hash = hash_password(new_password)
    except ValueError as exc:
        return templates.TemplateResponse(
            "users.html",
            {
                **_base_context(request),
                "users": db.scalars(select(User).order_by(User.id)).all(),
                "error": str(exc),
            },
            status_code=400,
        )
    db.commit()
    log_action(db, getattr(request.state, "user", None).id if getattr(request.state, "user", None) else None, "reset_password", {"user_id": user_id}, request.client.host if request.client else None, request.headers.get("user-agent"))
    return RedirectResponse(url="/users", status_code=303)


@router.post("/{user_id}/toggle-active")
async def toggle_active(
    user_id: int,
    request: Request,
    db: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
):
    user_obj = db.get(User, user_id)
    if user_obj:
        user_obj.is_active = not user_obj.is_active
        db.commit()
        log_action(db, getattr(request.state, "user", None).id if getattr(request.state, "user", None) else None, "toggle_active", {"user_id": user_id}, request.client.host if request.client else None, request.headers.get("user-agent"))
    return RedirectResponse(url="/users", status_code=303)
