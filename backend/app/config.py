from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    environment: str = "development"

    # OpenTelemetry — set OTLP_ENDPOINT to enable trace export to Jaeger
    # Default points at the Jaeger all-in-one container in Docker Compose
    otlp_endpoint: str = "http://jaeger:4317"
    # Set to "false" to disable OTel (e.g. in unit tests)
    otel_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
