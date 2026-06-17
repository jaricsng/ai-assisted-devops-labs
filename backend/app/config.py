from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_EXAMPLE_KEYS = {
    "change-me",
    "secret",
    "your-secret-key",
    "test-secret-key-for-local-dev-only",
}


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    environment: str = "development"

    # CORS — comma-separated list of allowed origins; override in production
    cors_origins: list[str] = ["http://localhost:5173"]

    # OpenTelemetry — set OTLP_ENDPOINT to enable trace export to Jaeger
    # Default points at the Jaeger all-in-one container in Docker Compose
    otlp_endpoint: str = "http://jaeger:4317"
    # Set to "false" to disable OTel (e.g. in unit tests)
    otel_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def validate_secret_key_in_production(self) -> "Settings":
        if self.environment == "production":
            if len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters in production."
                )
            if self.secret_key.lower() in _EXAMPLE_KEYS:
                raise ValueError(
                    "SECRET_KEY must not be an example or placeholder value in production."
                )
        return self


settings = Settings()
