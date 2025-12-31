from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    facturama_base_url: str = Field("https://apisandbox.facturama.mx", alias="FACTURAMA_BASE_URL")
    facturama_user: str = Field(..., alias="FACTURAMA_USER")
    facturama_password: SecretStr = Field(..., alias="FACTURAMA_PASSWORD")
    database_url: str = Field("sqlite:///./app.db", alias="DATABASE_URL")
    default_serie: str = Field("ML", alias="DEFAULT_SERIE")
    facturas_storage_dir: Path = Field(default=Path("./storage/facturas"), alias="FACTURAS_STORAGE_DIR")
    environment: str = Field("development", alias="ENVIRONMENT")
    secret_key: str = Field(..., alias="SECRET_KEY")
    session_cookie_name: str = Field("session", alias="SESSION_COOKIE_NAME")
    login_rate_limit_count: int = Field(5, alias="LOGIN_RATE_LIMIT_COUNT")
    login_rate_limit_window: int = Field(600, alias="LOGIN_RATE_LIMIT_WINDOW")  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    storage_dir = settings.facturas_storage_dir
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "xml").mkdir(exist_ok=True)
    (storage_dir / "pdf").mkdir(exist_ok=True)
    (storage_dir / "zip").mkdir(exist_ok=True)
    return settings


settings = get_settings()
