from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import setup_logging
from app.models.series import Series
from app.routers import ui

setup_logging()
app = FastAPI(title="Factura Global CFDI 4.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(ui.router)


@app.on_event("startup")
def ensure_default_series():
    with SessionLocal() as session:
        if settings.default_serie and not session.get(Series, settings.default_serie):
            session.add(Series(code=settings.default_serie, description="Serie por defecto", is_active=True))
            session.commit()
