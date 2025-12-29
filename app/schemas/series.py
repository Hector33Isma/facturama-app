from pydantic import BaseModel, Field


class SeriesBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=10)
    description: str
    is_active: bool = True


class SeriesCreate(SeriesBase):
    pass


class SeriesUpdate(BaseModel):
    description: str | None = None
    is_active: bool | None = None


class SeriesOut(SeriesBase):
    class Config:
        from_attributes = True
