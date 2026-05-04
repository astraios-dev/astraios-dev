from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    bybit_proxy: str = ""

    fernet_key: str = ""
    allowed_origins: str = "https://astraios.tech,http://localhost:5173"

    model_config = {"env_file": str(Path(__file__).resolve().parent.parent / ".env")}


settings = Settings()
