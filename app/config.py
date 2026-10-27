import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Google Flow API"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SESSION_STORAGE_PATH: str = os.getenv("SESSION_STORAGE_PATH", "auth/session.json")
    USER_DATA_DIR: str = os.getenv("USER_DATA_DIR", "auth/chrome_profile")
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
    GENERATION_TIMEOUT: int = int(os.getenv("GENERATION_TIMEOUT", "120"))

    class Config:
        env_file = ".env"

settings = Settings()
