from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "HDFC KYC Engine"
    api_version: str = "v1"
    debug: bool = False

    # PostgreSQL
    # Render provides "postgres://" or "postgresql://" — asyncpg needs "postgresql+asyncpg://"
    database_url: str = "postgresql+asyncpg://kyc:kyc_password@localhost:5432/kyc_db"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # MinIO — self-hosted S3 satisfies RBI data residency requirement
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "kyc-documents"
    minio_secure: bool = False

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str = "CHANGE_THIS_BEFORE_BANK_DEPLOYMENT"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # AES-256 PII encryption at rest — RBI IT framework §6.2
    encryption_key: str = "CHANGE_THIS_TO_A_FERNET_KEY"

    # "tesseract" (default) or "paddleocr" (better for Hindi/regional scripts)
    ocr_backend: str = "tesseract"

    # OpenAI — used ONLY for non-PII tasks in production (sales collateral, code gen).
    # For demo extraction: GPT-4o Vision reads documents when this key is set.
    # COMPLIANCE: Replace with on-premise model before bank deployment.
    openai_api_key: str = ""


settings = Settings()
