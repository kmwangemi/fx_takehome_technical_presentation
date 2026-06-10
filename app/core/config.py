from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )
    # Database
    DATABASE_URL: str
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


settings = Settings()  # type: ignore[call-arg]
