from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.db import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    status = Column(String(20), nullable=False)
    serie = Column(String(10), nullable=False)
    folio = Column(Integer, nullable=False)
    uuid = Column(String(64))
    facturama_id = Column(String(64))
    issue_date = Column(Date)
    excel_filename = Column(String(255))
    request_json = Column(Text)
    response_json = Column(Text)
    error_message = Column(Text)
    xml_path = Column(String(255))
    pdf_path = Column(String(255))

    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_code = Column(String(50))
    description = Column(String(255))
    unit_code = Column(String(20))
    unit = Column(String(50))
    quantity = Column(Numeric(18, 6))
    unit_price = Column(Numeric(18, 6))
    subtotal = Column(Numeric(18, 6))
    tax_object = Column(String(10))
    tax_total = Column(Numeric(18, 6))
    total = Column(Numeric(18, 6))
    identification_number = Column(String(100))

    invoice = relationship("Invoice", back_populates="items")
