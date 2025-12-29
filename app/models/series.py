from sqlalchemy import Boolean, Column, Integer, String

from app.core.db import Base


class Series(Base):
    __tablename__ = "series"

    code = Column(String(10), primary_key=True)
    description = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class SeriesCounter(Base):
    __tablename__ = "series_counters"

    series_code = Column(String(10), primary_key=True)
    last_folio = Column(Integer, nullable=False, default=0)
