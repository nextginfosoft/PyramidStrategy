from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ENCRYPTION_KEY: str = "dev-encryption-key-32-bytes!!!!"

    # Database
    DATABASE_URL: str = "sqlite:///./pyramidstrategy.db"

    # Redis
    USE_FAKE_REDIS: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"

    # Paper Trade
    PAPER_TRADE: bool = True

    # Zerodha (runtime, from DB — these are fallback only)
    KITE_API_KEY: Optional[str] = None
    KITE_API_SECRET: Optional[str] = None

    # AI
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Notifications
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://pyramid-strategy.vercel.app",
    ]

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if len(v.encode()) < 16:
            raise ValueError("ENCRYPTION_KEY must be at least 16 bytes")
        # Pad or truncate to exactly 32 bytes for AES-256
        key_bytes = v.encode("utf-8")
        return key_bytes[:32].ljust(32, b"\0").decode("latin-1")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
