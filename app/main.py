from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.session import (
    ensure_csrf,
    ensure_session_exp,
    is_session_expired,
    load_session,
    save_session,
    clear_session,
)
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import setup_logging
from app.models.series import Series
from app.routers import ui, auth, users

setup_logging()
docs_kwargs = {}
if settings.environment.lower() == "production":
    docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Factura Global CFDI 4.0", **docs_kwargs)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(ui.router)

allowed_origins = settings.cors_allowed_origins
if settings.environment.lower() == "production":
    allowed_origins = ["https://facturas.refacciones.site"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"] if settings.environment.lower() != "production" else ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_data = load_session(request)
    if is_session_expired(session_data):
        session_data = {}
        request.state.clear_session = True
    request.state.session = session_data
    request.state.session_changed = False
    _, created = ensure_csrf(session_data)
    if created:
        request.state.session_changed = True
    if ensure_session_exp(session_data):
        request.state.session_changed = True
    response = await call_next(request)
    if getattr(request.state, "clear_session", False):
        clear_session(response)
    elif getattr(request.state, "session_changed", False):
        save_session(response, request.state.session)
    return response


@app.on_event("startup")
def ensure_default_series():
    with SessionLocal() as session:
        if settings.default_serie and not session.get(Series, settings.default_serie):
            session.add(Series(code=settings.default_serie, description="Serie por defecto", is_active=True))
            session.commit()
