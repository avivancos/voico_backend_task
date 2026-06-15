import os

from pydantic import Field
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

    # OpenAI enrichment runs inside the webhook request, so the client MUST bound its latency: a
    # finite per-request timeout and limited retries (worst case ~timeout * (1 + retries)) instead of
    # the SDK's 600s default. gt=0 / ge=0 so a misconfig fails fast at boot.
    openai_timeout_seconds: float = Field(default=20.0, gt=0)
    openai_max_retries: int = Field(default=1, ge=0)

    # Comma-separated CORS allow-list. Never use "*" together with credentials.
    allowed_origins: str = "http://localhost:5173"

    # Stale-call auto-expiry (Task 3): how often the sweep runs, and how long a call may sit
    # in_progress before it is force-failed. Env-tunable (e.g. EXPIRY_THRESHOLD_MINUTES=1) so the
    # job can be exercised without editing code.
    expiry_interval_minutes: float = Field(default=10, gt=0)
    expiry_threshold_minutes: float = Field(default=30, gt=0)

    # Webhook security (Task 4). Empty secret = opt-in: the webhook accepts unsigned requests (dev /
    # the README Swagger demo). When set, every request must carry a valid HMAC-SHA256 `X-Signature`
    # over `"{X-Timestamp}.{raw_body}"` and an `X-Timestamp` within `webhook_tolerance_seconds`
    # (replay window). See app/modules/calls/security.py and ADR-0007.
    webhook_secret: str = ""
    webhook_tolerance_seconds: int = Field(default=300, gt=0)

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
