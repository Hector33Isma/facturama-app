import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_session
from app.dependencies import csrf_protect, require_login
from app.models.invoice import Invoice
from app.models.series import Series, SeriesCounter
from app.services.facturama_client import FacturamaClient, FacturamaError
from app.services.invoicing_service import InvoicingService

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(dependencies=[Depends(require_login)])


def _storage_uploads_dir() -> Path:
    uploads = settings.facturas_storage_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


def _ctx(request: Request, extra: dict | None = None):
    base = {
        "request": request,
        "user": getattr(request.state, "user", None),
        "csrf_token": request.state.session.get("csrf_token"),
    }
    if extra:
        base.update(extra)
    return base


@router.get("/")
async def home(request: Request, session: Session = Depends(get_session)):
    series = session.scalars(select(Series).order_by(Series.code)).all()
    selected = settings.default_serie if any(s.code == settings.default_serie for s in series) else (series[0].code if series else "")
    return templates.TemplateResponse(
        "timbrar.html",
        _ctx(
            request,
            {
                "series": series,
                "selected_serie": selected,
                "today": date.today().isoformat(),
            },
        ),
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
    csrf=Depends(csrf_protect),
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
            _ctx(
                request,
                {
                    "series": series,
                    "selected_serie": serie,
                    "error": "No se pudo guardar el archivo. Intenta de nuevo.",
                    "today": date.today().isoformat(),
                },
            ),
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
    context = {
        "series": series,
        "selected_serie": serie,
        "today": date.today().isoformat(),
    }
    if result.get("success"):
        context["message"] = f"Factura timbrada correctamente. Serie {serie}, Folio {result.get('folio')}"
    else:
        context["error"] = result.get("errors") or ["Hubo errores al procesar el archivo."]
        if result.get("error_excel"):
            context["error_excel"] = result["error_excel"]
    return templates.TemplateResponse("timbrar.html", _ctx(request, context))


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
        _ctx(
            request,
            {
                "invoices": invoices,
                "series": series,
                "filters": {"date_start": date_start, "date_end": date_end, "serie": serie, "status": status},
                "file_map": file_map,
            },
        ),
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
    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "series.html",
        _ctx(
            request,
            {
                "series": series,
                "counters": counters,
                "msg": msg,
                "error": error,
            },
        ),
    )


@router.post("/series")
async def series_create(
    request: Request,
    code: str = Form(...),
    description: str = Form(...),
    is_active: Optional[bool] = Form(False),
    session: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
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
async def series_toggle(code: str, session: Session = Depends(get_session), csrf=Depends(csrf_protect)):
    series = session.get(Series, code)
    if series:
        series.is_active = not series.is_active
        session.commit()
    return RedirectResponse(url="/series", status_code=303)


@router.post("/series/{code}/folio")
async def series_update_folio(
    code: str,
    last_folio: str = Form(...),
    session: Session = Depends(get_session),
    csrf=Depends(csrf_protect),
):
    series = session.get(Series, code)
    if not series:
        return RedirectResponse(url="/series?error=Serie no encontrada", status_code=303)
    try:
        value = int(last_folio)
        if value < 0:
            raise ValueError("Debe ser >= 0")
    except Exception:
        return RedirectResponse(url="/series?error=Último folio inválido", status_code=303)
    counter = session.get(SeriesCounter, code)
    if not counter:
        counter = SeriesCounter(series_code=code, last_folio=value)
        session.add(counter)
    else:
        counter.last_folio = value
    session.commit()
    return RedirectResponse(url="/series?msg=Último folio actualizado", status_code=303)


@router.get("/consultar")
async def consultar_form(request: Request):
    return templates.TemplateResponse(
        "consultar.html",
        _ctx(request, {"results": []}),
    )


@router.post("/consultar")
async def consultar(
    request: Request,
    date_start: str = Form(...),
    date_end: str = Form(...),
    csrf=Depends(csrf_protect),
):
    client = FacturamaClient()
    error = None
    results = []
    debug = None
    try:
        resp = await client.list_cfdis(date_start=date_start, date_end=date_end)
        if isinstance(resp, dict) and "Data" in resp:
            results = resp.get("Data") or []
        elif isinstance(resp, list):
            results = resp
        else:
            error = "Respuesta inesperada de Facturama."
            debug = {
                "status_code": None,
                "url": None,
                "response_text": json.dumps(resp, ensure_ascii=False, indent=2),
                "exception": None,
            }
    except FacturamaError as exc:
        error = "No se pudieron consultar CFDIs."
        response_text = ""
        details = exc.details
        if isinstance(details, dict) and "response" in details:
            response_text = json.dumps(details.get("response"), ensure_ascii=False, indent=2)
        elif isinstance(details, dict):
            response_text = json.dumps(details, ensure_ascii=False, indent=2)
        elif isinstance(details, str):
            response_text = details
        debug = {
            "status_code": exc.status_code,
            "url": exc.url,
            "response_text": response_text,
            "exception": str(exc),
        }
    except Exception as exc:
        error = "Error inesperado al consultar CFDIs."
        debug = {
            "status_code": None,
            "url": None,
            "response_text": "",
            "exception": str(exc),
        }
    return templates.TemplateResponse(
        "consultar.html",
        _ctx(
            request,
            {
                "results": results,
                "error": error,
                "filters": {"date_start": date_start, "date_end": date_end},
                "debug": debug,
            },
        ),
    )
