from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class InvoiceItemOut(BaseModel):
    product_code: Optional[str] = None
    description: Optional[str] = None
    unit_code: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    subtotal: Optional[float] = None
    tax_object: Optional[str] = None
    tax_total: Optional[float] = None
    total: Optional[float] = None
    identification_number: Optional[str] = None

    class Config:
        from_attributes = True


class InvoiceOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    serie: str
    folio: int
    uuid: Optional[str] = None
    facturama_id: Optional[str] = None
    issue_date: Optional[date] = None
    excel_filename: Optional[str] = None
    xml_path: Optional[str] = None
    pdf_path: Optional[str] = None
    error_message: Optional[str] = None
    items: List[InvoiceItemOut] = []

    class Config:
        from_attributes = True
