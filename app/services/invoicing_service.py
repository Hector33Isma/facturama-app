import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.invoice import Invoice, InvoiceItem
from app.services.excel_service import ExcelService, ExcelProcessingResult
from app.services.facturama_client import FacturamaClient, FacturamaError
from app.services.folio_service import FolioService, FolioServiceError


class InvoicingService:
    def __init__(self, session: Session):
        self.session = session
        self.folio_service = FolioService(session)
        self.excel_service = ExcelService()
        self.facturama = FacturamaClient()

    async def process_invoice(
        self,
        excel_path: Path,
        serie: str,
        issue_date: date,
        expedition_place: Optional[str] = None,
        observations: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            next_folio = self.folio_service.next_folio(serie)
        except FolioServiceError as exc:
            return {"success": False, "errors": [str(exc)]}

        excel_result: ExcelProcessingResult = self.excel_service.process(
            excel_path, serie=serie, folio=next_folio, issue_date=issue_date, expedition_place=expedition_place, observations=observations
        )
        if not excel_result.valid:
            return {
                "success": False,
                "errors": excel_result.errors,
                "error_excel": str(excel_result.error_excel_path) if excel_result.error_excel_path else None,
            }

        payload = excel_result.payload or {}
        invoice = Invoice(
            status="pending",
            serie=serie,
            folio=next_folio,
            issue_date=issue_date,
            excel_filename=excel_path.name,
            request_json=json.dumps(payload, ensure_ascii=False),
        )
        self.session.add(invoice)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return {"success": False, "errors": [f"El folio {next_folio} de la serie {serie} ya existe. Intenta de nuevo."]}

        try:
            response = await self.facturama.create_cfdi(payload)
            invoice.response_json = json.dumps(response, ensure_ascii=False)
            invoice.status = "success"
            invoice.facturama_id = response.get("Id") or response.get("id")
            invoice.uuid = response.get("Uuid") or response.get("uuid")
            self._persist_items(invoice, payload.get("Items", []))
            self.folio_service.commit_folio(serie, next_folio)

            await self._store_files(invoice)
            self.session.commit()
            return {
                "success": True,
                "invoice_id": invoice.id,
                "serie": serie,
                "folio": next_folio,
                "uuid": invoice.uuid,
                "facturama_id": invoice.facturama_id,
            }
        except FacturamaError as exc:
            logger.warning("FacturamaError: %s", exc)
            invoice.status = "failed"
            invoice.error_message = str(exc)
            invoice.response_json = json.dumps({"error": exc.details}, ensure_ascii=False)
            self.session.commit()
            errors = self._format_facturama_errors(exc)
            return {"success": False, "errors": errors}
        except Exception as exc:
            logger.exception("Error inesperado al timbrar")
            invoice.status = "failed"
            invoice.error_message = str(exc)
            self.session.commit()
            return {"success": False, "errors": ["Error inesperado, revisa logs"]}

    def _persist_items(self, invoice: Invoice, items_data):
        for item in items_data:
            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                product_code=item.get("ProductCode"),
                description=item.get("Description"),
                unit_code=item.get("UnitCode"),
                unit=item.get("Unit"),
                quantity=item.get("Quantity"),
                unit_price=item.get("UnitPrice"),
                subtotal=item.get("Subtotal"),
                tax_object=item.get("TaxObject"),
                tax_total=(item.get("Taxes") or [{}])[0].get("Total") if item.get("Taxes") else None,
                total=item.get("Total"),
                identification_number=item.get("IdentificationNumber"),
            )
            self.session.add(inv_item)

    async def _store_files(self, invoice: Invoice) -> None:
        if not invoice.facturama_id:
            logger.warning("No Facturama ID, skip descarga de archivos")
            return
        try:
            pdf_path = settings.facturas_storage_dir / "pdf" / f"{invoice.serie}-{invoice.folio}.pdf"
            xml_path = settings.facturas_storage_dir / "xml" / f"{invoice.serie}-{invoice.folio}.xml"
            zip_path = settings.facturas_storage_dir / "zip" / f"{invoice.serie}-{invoice.folio}.zip"
            pdf_saved = await self.facturama.download_document(invoice.facturama_id, "pdf", str(pdf_path))
            xml_saved = await self.facturama.download_document(invoice.facturama_id, "xml", str(xml_path))
            zip_saved = await self.facturama.download_zip(invoice.facturama_id, str(zip_path))
            if pdf_saved:
                invoice.pdf_path = str(pdf_path)
            if xml_saved:
                invoice.xml_path = str(xml_path)
            if not zip_saved:
                logger.warning("No se pudo obtener ZIP para CFDI %s", invoice.facturama_id)
        except FacturamaError as exc:
            logger.warning("No se pudieron descargar archivos: %s", exc)

    def _format_facturama_errors(self, exc: FacturamaError) -> list[str]:
        errors: list[str] = []
        status_txt = f"(HTTP {exc.status_code})" if exc.status_code else ""
        base_msg = "Error al timbrar factura"
        if status_txt:
            base_msg = f"{base_msg} {status_txt}"
        if isinstance(exc.details, dict):
            msg = exc.details.get("Message") or exc.details.get("message") or ""
            if msg:
                errors.append(msg)
            model_state = exc.details.get("ModelState")
            if isinstance(model_state, dict):
                for key, vals in model_state.items():
                    if isinstance(vals, list):
                        for v in vals:
                            errors.append(f"{key}: {v}")
                    else:
                        errors.append(f"{key}: {vals}")
        elif isinstance(exc.details, str):
            errors.append(exc.details)
        if not errors:
            errors.append(str(exc))
        errors.insert(0, base_msg)
        return errors
