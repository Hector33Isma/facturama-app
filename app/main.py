from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.session import ensure_csrf, load_session, save_session, clear_session
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import setup_logging
from app.models.series import Series
from app.routers import ui, auth, users

setup_logging()
app = FastAPI(title="Factura Global CFDI 4.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(ui.router)


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_data = load_session(request)
    request.state.session = session_data
    request.state.session_changed = False
    _, created = ensure_csrf(session_data)
    if created:
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
