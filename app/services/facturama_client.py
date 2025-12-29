import base64
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from app.core.config import settings


class FacturamaError(Exception):
    def __init__(self, message: str, status_code: int | None = None, details: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class FacturamaClient:
    def __init__(self):
        self.base_url = settings.facturama_base_url.rstrip("/")
        self.auth = (settings.facturama_user, settings.facturama_password.get_secret_value())
        self.timeout = httpx.Timeout(30.0)

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(auth=self.auth, timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, **kwargs)
            except httpx.RequestError as exc:
                logger.exception("HTTP request error to Facturama")
                raise FacturamaError("No se pudo contactar Facturama", details=str(exc)) from exc

        if response.status_code >= 400:
            detail: Any | None = None
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            logger.warning("Facturama API error {}: {}", response.status_code, detail)
            message = "Error de Facturama"
            if isinstance(detail, dict):
                message = detail.get("Message") or detail.get("message") or message
            elif isinstance(detail, str) and detail:
                message = detail
            raise FacturamaError(message, status_code=response.status_code, details=detail)
        if "application/json" in response.headers.get("content-type", ""):
            return response.json()
        return {"raw": response.content}

    async def create_cfdi(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/3/cfdis", json=payload)

    async def list_cfdis(self, date_start: str, date_end: str, cfdi_type: str = "issued") -> Dict[str, Any]:
        params = {"type": cfdi_type, "dateStart": date_start, "dateEnd": date_end}
        return await self._request("GET", "/cfdi", params=params)

    async def download_document(
        self, cfdi_id: str, fmt: str, target_path: Optional[str] = None, cfdi_type: str = "issued"
    ) -> Optional[str]:
        fmt_lower = fmt.lower()
        if fmt_lower not in {"pdf", "xml"}:
            raise FacturamaError(f"Formato no soportado: {fmt}")
        path = f"/api/Cfdi/{fmt_lower}/{cfdi_type}/{cfdi_id}"
        try:
            data = await self._request("GET", path)
        except FacturamaError as exc:
            if exc.status_code == 404:
                logger.warning("No se encontró %s para CFDI %s (404)", fmt_upper := fmt_lower.upper(), cfdi_id)
                return None
            raise
        content_b64 = data.get("Content") or data.get("content")
        if not content_b64:
            logger.warning("Facturama no devolvió contenido para %s (%s)", cfdi_id, fmt)
            return None
        if target_path:
            try:
                decoded = base64.b64decode(content_b64)
                path_obj = Path(target_path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                with open(path_obj, "wb") as f:
                    f.write(decoded)
            except Exception as exc:
                logger.exception("No se pudo escribir archivo %s", target_path)
                raise FacturamaError("No se pudo guardar archivo descargado", details=str(exc)) from exc
            return target_path
        return content_b64

    async def download_zip(
        self, cfdi_id: str, target_path: Optional[str] = None, cfdi_type: str = "issued"
    ) -> Optional[str]:
        path = f"/cfdi/zip"
        try:
            data = await self._request("GET", path, params={"id": cfdi_id, "type": cfdi_type})
        except FacturamaError as exc:
            if exc.status_code == 404:
                logger.warning("No se encontró ZIP para CFDI %s (404)", cfdi_id)
                return None
            raise
        content_b64 = data.get("Content") or data.get("content")
        if not content_b64:
            logger.warning("Facturama no devolvió contenido ZIP para %s", cfdi_id)
            return None
        if target_path:
            try:
                decoded = base64.b64decode(content_b64)
                path_obj = Path(target_path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                with open(path_obj, "wb") as f:
                    f.write(decoded)
            except Exception as exc:
                logger.exception("No se pudo escribir ZIP %s", target_path)
                raise FacturamaError("No se pudo guardar ZIP descargado", details=str(exc)) from exc
            return target_path
        return content_b64
