from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from app.core.config import settings


EXPECTED_COLUMNS = [
    "Folio",
    "No. Factura",
    "Razon Social",
    "RFC",
    "Fiscal Regime",
    "UsoCFDI",
    "Calle",
    "Colonia",
    "No. Exterior",
    "No. Interior",
    "CP",
    "Municipio",
    "Estado",
    "Forma de Pago",
    "Condiciones de Pago",
    "Metodo de Pago",
    "Observaciones",
    "ClaveProdServ",
    "Concepto",
    "ClaveUnidad",
    "Unidad",
    "Cantidad",
    "Precio Unitario",
    "Objeto Impuesto",
    "Subtotal del Concepto",
    "IVA del Concepto",
    "Total del Concepto",
    "Pedido",
    "Periodicidad",
    "Mes",
    "Year",
    "Mail",
]


@dataclass
class ExcelProcessingResult:
    valid: bool
    errors: List[str]
    payload: Optional[Dict[str, Any]] = None
    error_excel_path: Optional[Path] = None


def normalize_payment_form(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        as_int = int(str(value).split(".")[0])
        return f"{as_int:02d}"
    except (ValueError, TypeError):
        return str(value).strip()


def normalize_cp(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{int(str(value).split('.')[0]):05d}"
    except (ValueError, TypeError):
        cp = str(value).strip()
        return cp.zfill(5) if cp.isdigit() else cp


def to_decimal(value: Any) -> Decimal:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return Decimal("0")
    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidOperation(f"No es un número válido: {value}")


class ExcelService:
    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or settings.facturas_storage_dir

    def _validate_columns(self, df: pd.DataFrame) -> List[str]:
        missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
        return missing

    def process(
        self,
        excel_path: Path,
        serie: str,
        folio: int,
        issue_date: date,
        expedition_place: Optional[str] = None,
        observations: Optional[str] = None,
    ) -> ExcelProcessingResult:
        errors: List[str] = []
        try:
            df = pd.read_excel(excel_path, dtype=str)
        except Exception as exc:  # broad: excel parsing errors
            logger.exception("No se pudo leer el Excel %s", excel_path)
            return ExcelProcessingResult(False, [f"No se pudo leer el Excel: {exc}"])

        missing = self._validate_columns(df)
        if missing:
            return ExcelProcessingResult(False, [f"Faltan columnas requeridas: {', '.join(missing)}"])

        # Keep numeric fields as decimals
        df_numbers = pd.read_excel(excel_path)
        error_rows: List[str] = []
        items: List[Dict[str, Any]] = []
        tolerance = Decimal("0.02")

        for idx, row in df.iterrows():
            row_num = idx + 2  # account header
            row_errors = []
            numeric_row = df_numbers.iloc[idx]

            def _dec(col: str) -> Decimal:
                try:
                    return to_decimal(numeric_row[col])
                except InvalidOperation as exc:
                    row_errors.append(f"{col}: {exc}")
                    return Decimal("0")

            quantity = _dec("Cantidad")
            subtotal = _dec("Subtotal del Concepto")
            iva = _dec("IVA del Concepto")
            total = _dec("Total del Concepto")

            if quantity <= 0:
                row_errors.append("Cantidad debe ser mayor a 0")
            if subtotal < 0 or iva < 0 or total < 0:
                row_errors.append("Importes no pueden ser negativos")

            if (total - (subtotal + iva)).copy_abs() > tolerance:
                row_errors.append("Total no cuadra con Subtotal + IVA (tolerancia 0.02)")

            identification_number = str(row.get("Pedido", "")).strip()
            if not identification_number:
                row_errors.append("Pedido es obligatorio (IdentificationNumber)")

            tax_object = str(row.get("Objeto Impuesto", "")).strip()
            product_code = str(row.get("ClaveProdServ", "")).strip()
            unit_code = str(row.get("ClaveUnidad", "")).strip()
            if not product_code:
                row_errors.append("ClaveProdServ requerida")
            if not unit_code:
                row_errors.append("ClaveUnidad requerida")
            if not tax_object:
                row_errors.append("Objeto Impuesto requerido")

            if row_errors:
                error_rows.append(f"Fila {row_num}: " + "; ".join(row_errors))

            item = {
                "ProductCode": product_code,
                "Description": str(row.get("Concepto", "")).strip(),
                "IdentificationNumber": identification_number,
                "UnitCode": unit_code,
                "Unit": str(row.get("Unidad", "")).strip(),
                "Quantity": float(quantity),
                "UnitPrice": float(to_decimal(numeric_row["Precio Unitario"])),
                "Subtotal": float(subtotal),
                "TaxObject": tax_object,
                "Taxes": [],
                "Total": float(total),
            }
            if iva > 0:
                item["Taxes"].append(
                    {
                        "Name": "IVA",
                        "Rate": 0.16,
                        "IsRetention": False,
                        "Base": float(subtotal),
                        "Total": float(iva),
                    }
                )
            items.append(item)

        if error_rows:
            errors.extend(error_rows)
            error_excel_path = self._build_error_excel(df, error_rows, excel_path)
            return ExcelProcessingResult(False, errors, error_excel_path=error_excel_path)

        payment_form = normalize_payment_form(df.iloc[0]["Forma de Pago"])
        payment_method = str(df.iloc[0]["Metodo de Pago"]).strip().upper()
        if payment_method not in {"PUE", "PPD"}:
            errors.append("Metodo de Pago debe ser PUE o PPD")
        expedition_cp = normalize_cp(expedition_place or df.iloc[0]["CP"])
        if not expedition_cp:
            errors.append("Código Postal (Lugar de expedición) requerido")

        if issue_date < date.today() - timedelta(days=2):
            errors.append("Fecha de emisión no puede ser mayor a 2 días atrás")

        if errors:
            return ExcelProcessingResult(False, errors)

        payload = {
            "Serie": serie,
            "Folio": folio,
            "CfdiType": "I",
            "PaymentForm": payment_form,
            "PaymentMethod": payment_method,
            "ExpeditionPlace": expedition_cp,
            "Currency": "MXN",
            "Date": issue_date.isoformat(),
            "Observations": observations or str(df.iloc[0].get("Observaciones", "")).strip(),
            "Receiver": {
                "Rfc": str(df.iloc[0]["RFC"]).strip(),
                "Name": str(df.iloc[0]["Razon Social"]).strip(),
                "CfdiUse": str(df.iloc[0]["UsoCFDI"]).strip(),
                "FiscalRegime": str(df.iloc[0]["Fiscal Regime"]).strip(),
                "TaxZipCode": normalize_cp(df.iloc[0]["CP"]),
                "Email": str(df.iloc[0].get("Mail", "")).strip(),
            },
            "GlobalInformation": {
                "Periodicity": str(df.iloc[0]["Periodicidad"]).strip(),
                "Months": str(df.iloc[0]["Mes"]).strip(),
                "Year": int(to_decimal(df_numbers.iloc[0]["Year"])),
            },
            "Items": items,
        }

        return ExcelProcessingResult(True, [], payload=payload)

    def _build_error_excel(self, df: pd.DataFrame, row_errors: List[str], source_path: Path) -> Path:
        df_errors = df.copy()
        error_col: List[str] = [""] * len(df_errors)
        for err in row_errors:
            # err format: "Fila 3: msg"
            try:
                parts = err.split(":")
                row_num = int(parts[0].replace("Fila", "").strip())
                idx = row_num - 2
                error_col[idx] = parts[1].strip()
            except Exception:
                logger.debug("No se pudo mapear error a fila: %s", err)
        df_errors["Errores"] = error_col
        target = self.storage_dir / f"{source_path.stem}_errores.xlsx"
        try:
            df_errors.to_excel(target, index=False)
        except Exception as exc:
            logger.exception("No se pudo generar Excel de errores")
            target = source_path.with_name(source_path.stem + "_errores_fallback.xlsx")
            df_errors.to_excel(target, index=False)
        return target
