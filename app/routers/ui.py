from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_session
from app.models.invoice import Invoice
from app.models.series import Series, SeriesCounter
from app.services.facturama_client import FacturamaClient, FacturamaError
from app.services.invoicing_service import InvoicingService

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


def _storage_uploads_dir() -> Path:
    uploads = settings.facturas_storage_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


@router.get("/")
async def home(request: Request, session: Session = Depends(get_session)):
    series = session.scalars(select(Series).order_by(Series.code)).all()
    selected = settings.default_serie if any(s.code == settings.default_serie for s in series) else (series[0].code if series else "")
    return templates.TemplateResponse(
        "timbrar.html",
        {"request": request, "series": series, "selected_serie": selected, "today": date.today().isoformat()},
    )


@router.post("/timbrar")
async def timbrar(
    request: Request,
    serie: str = Form(...),
    issue_date: str = Form(...),
    expedition_place: Optional[str] = Form(None),
    observations: Optional[str] = Form(None),
    excel_file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    series = session.scalars(select(Series).order_by(Series.code)).all()
    parsed_date = date.fromisoformat(issue_date)
    upload_dir = _storage_uploads_dir()
    temp_path = upload_dir / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{excel_file.filename}"
    try:
        content = await excel_file.read()
        temp_path.write_bytes(content)
    except Exception:
        return templates.TemplateResponse(
            "timbrar.html",
            {
                "request": request,
                "series": series,
                "selected_serie": serie,
                "error": "No se pudo guardar el archivo. Intenta de nuevo.",
                "today": date.today().isoformat(),
            },
            status_code=400,
        )

    service = InvoicingService(session)
    result = await service.process_invoice(
        excel_path=temp_path,
        serie=serie,
        issue_date=parsed_date,
        expedition_place=expedition_place,
        observations=observations,
    )
    context = {"request": request, "series": series, "selected_serie": serie, "today": date.today().isoformat()}
    if result.get("success"):
        context["message"] = f"Factura timbrada correctamente. Serie {serie}, Folio {result.get('folio')}"
    else:
        context["error"] = result.get("errors") or ["Hubo errores al procesar el archivo."]
        if result.get("error_excel"):
            context["error_excel"] = result["error_excel"]
    return templates.TemplateResponse("timbrar.html", context)


@router.get("/historial")
async def historial(
    request: Request,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    serie: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(Invoice)
    if date_start:
        stmt = stmt.where(Invoice.created_at >= datetime.fromisoformat(date_start))
    if date_end:
        stmt = stmt.where(Invoice.created_at <= datetime.fromisoformat(date_end) + timedelta(days=1))
    if serie:
        stmt = stmt.where(Invoice.serie == serie)
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.created_at.desc())
    invoices = session.scalars(stmt).all()
    series = session.scalars(select(Series).order_by(Series.code)).all()
    file_map = {}
    for inv in invoices:
        pdf_ok = bool(inv.pdf_path and Path(inv.pdf_path).exists())
        xml_ok = bool(inv.xml_path and Path(inv.xml_path).exists())
        zip_ok = (settings.facturas_storage_dir / "zip" / f"{inv.serie}-{inv.folio}.zip").exists()
        file_map[inv.id] = {"pdf": pdf_ok, "xml": xml_ok, "zip": zip_ok}
    return templates.TemplateResponse(
        "historial.html",
        {
            "request": request,
            "invoices": invoices,
            "series": series,
            "filters": {"date_start": date_start, "date_end": date_end, "serie": serie, "status": status},
            "file_map": file_map,
        },
    )


@router.get("/download/{invoice_id}/{fmt}")
async def download(invoice_id: int, fmt: str, session: Session = Depends(get_session)):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/historial", status_code=302)
    if fmt == "zip":
        path = settings.facturas_storage_dir / "zip" / f"{invoice.serie}-{invoice.folio}.zip"
    else:
        path = invoice.pdf_path if fmt == "pdf" else invoice.xml_path
    if not path or not Path(path).exists():
        return RedirectResponse(url="/historial", status_code=302)
    if fmt == "pdf":
        media_type = "application/pdf"
    elif fmt == "zip":
        media_type = "application/zip"
    else:
        media_type = "application/xml"
    filename = Path(path).name
    return FileResponse(path, media_type=media_type, filename=filename)


@router.get("/series")
async def series_list(request: Request, session: Session = Depends(get_session)):
    series = session.scalars(select(Series).order_by(Series.code)).all()
    counters = {c.series_code: c.last_folio for c in session.scalars(select(SeriesCounter)).all()}
    return templates.TemplateResponse(
        "series.html",
        {"request": request, "series": series, "counters": counters},
    )


@router.post("/series")
async def series_create(
    request: Request,
    code: str = Form(...),
    description: str = Form(...),
    is_active: Optional[bool] = Form(False),
    session: Session = Depends(get_session),
):
    existing = session.get(Series, code)
    if existing:
        existing.description = description
        existing.is_active = is_active
    else:
        session.add(Series(code=code, description=description, is_active=is_active))
    session.commit()
    return RedirectResponse(url="/series", status_code=303)


@router.post("/series/{code}/toggle")
async def series_toggle(code: str, session: Session = Depends(get_session)):
    series = session.get(Series, code)
    if series:
        series.is_active = not series.is_active
        session.commit()
    return RedirectResponse(url="/series", status_code=303)


@router.get("/consultar")
async def consultar_form(request: Request):
    return templates.TemplateResponse("consultar.html", {"request": request})


@router.post("/consultar")
async def consultar(
    request: Request,
    date_start: str = Form(...),
    date_end: str = Form(...),
):
    client = FacturamaClient()
    error = None
    results = None
    try:
        results = await client.list_cfdis(date_start=date_start, date_end=date_end)
    except FacturamaError as exc:
        error = f"No se pudieron consultar CFDIs: {exc}"
    return templates.TemplateResponse(
        "consultar.html",
        {"request": request, "results": results, "error": error, "filters": {"date_start": date_start, "date_end": date_end}},
    )
