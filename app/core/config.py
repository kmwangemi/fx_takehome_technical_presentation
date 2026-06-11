from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )
    # Database
    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    # Rates API
    EXCHANGE_RATES_API_KEY: str = ""
    EXCHANGE_RATES_API_URL: str = "https://api.exchangeratesapi.io/v1/latest"
    # Spread & rates config
    DEFAULT_SPREAD_BPS: int = 50
    RATE_POLL_INTERVAL_SECONDS: int = 300
    MAX_RATE_STALENESS_SECONDS: int = 3600
    RATE_FETCH_TIMEOUT_SECONDS: int = 5
    # Quote TTL
    QUOTE_TTL_SECONDS: int = 60
    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "FX Engine System API"
    APP_VERSION: str = "1.0.0"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()  # type: ignore[call-arg]
