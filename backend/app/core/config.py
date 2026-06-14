import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The dotenv source is itself overridable via ENV_FILE so the test harness can disable it and run
    # on pure defaults — a developer's local .env can never change test outcomes. Unset -> ".env".
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env") or None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./db.sqlite3"
    openai_api_key: str = ""
    app_name: str = "Voico Calls Dashboard"

    # Comma-separated CORS allow-list. Never use "*" together with credentials.
    allowed_origins: str = "http://localhost:5173"

    # Stale-call auto-expiry (Task 3): how often the sweep runs, and how long a call may sit
    # in_progress before it is force-failed. Env-tunable (e.g. EXPIRY_THRESHOLD_MINUTES=1) so the
    # job can be exercised without editing code.
    expiry_interval_minutes: float = 10
    expiry_threshold_minutes: float = 30

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
