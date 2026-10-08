from typing import Any, List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Calaro AI"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = (
        "your-secret-key-change-this-for-production"  # Should be overridden in .env
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours; the app also signs out after inactivity

    # Observability
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    METRICS_REFRESH_SECONDS: int = 60
    MONITORING_SESSION_HOURS: int = 2

    # Abuse protection
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_MAX_FAILURES: int = 5          # per email, then locked
    LOGIN_LOCK_MINUTES: int = 15
    LOGIN_MAX_FAILURES_PER_IP: int = 30  # across all emails, same window
    REGISTER_PER_HOUR_PER_IP: int = 10
    RESET_REQUESTS_PER_15_MIN: int = 5
    VAANI_PER_MINUTE: int = 30

    # Database (MongoDB)
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "calaro"

    # The one and only super-admin. Created/enforced on every startup.
    SUPERADMIN_EMAIL: str = "calaro@admin.calaro.com"
    SUPERADMIN_PASSWORD: Optional[str] = None  # required on first start; ignored once the account exists

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v

    # AI
    OPENAI_API_KEY: str = "sk-placeholder"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:latest"
    WHISPER_MODEL: str = "base"

    # Bhashini. New dashboard gives an "Udyat key" + an "Inference" key.
    BHASHINI_INFERENCE_API_KEY: Optional[str] = None
    BHASHINI_UDYAT_KEY: Optional[str] = None
    # Older ULCA accounts: User ID + ULCA API key (optional)
    BHASHINI_USER_ID: Optional[str] = None
    BHASHINI_API_KEY: Optional[str] = None
    BHASHINI_SERVICE_IDS: Optional[str] = None  # JSON overrides, see bhashini_service.py
    BHASHINI_PIPELINE_ID: str = "64392f96daac500b55c543cd"  # MeitY pipeline
    BHASHINI_TTS_GENDER: str = "female"
    BHASHINI_TTS_SAMPLING_RATE: Optional[int] = 22050

    @field_validator("BHASHINI_TTS_SAMPLING_RATE", mode="before")
    @classmethod
    def _blank_rate(cls, v: Any) -> Any:
        return None if v in ("", None) else v

    # SMTP Configuration
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = 587
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: Optional[str] = "Calaro Security"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
