from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.series import Series, SeriesCounter


class FolioServiceError(Exception):
    pass


class FolioService:
    def __init__(self, session: Session):
        self.session = session

    def ensure_series(self, code: str) -> Series:
        series = self.session.get(Series, code)
        if not series:
            raise FolioServiceError(f"La serie {code} no existe")
        if not series.is_active:
            raise FolioServiceError(f"La serie {code} está inactiva")
        return series

    def next_folio(self, code: str) -> int:
        self.ensure_series(code)
        counter = self.session.get(SeriesCounter, code)
        max_invoice_folio = (
            self.session.scalar(select(func.max(Invoice.folio)).where(Invoice.serie == code)) or 0
        )
        if not counter:
            counter = SeriesCounter(series_code=code, last_folio=max_invoice_folio)
            self.session.add(counter)
            self.session.flush()
        last_folio = max(counter.last_folio, max_invoice_folio)
        return last_folio + 1

    def commit_folio(self, code: str, folio: int) -> None:
        counter = self.session.get(SeriesCounter, code)
        if not counter:
            counter = SeriesCounter(series_code=code, last_folio=folio)
            self.session.add(counter)
        elif folio > counter.last_folio:
            counter.last_folio = folio
        self.session.flush()

    def list_series(self):
        stmt = select(Series).order_by(Series.code)
        return self.session.scalars(stmt).all()
