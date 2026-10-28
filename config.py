from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Fullstack Platform API"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/platform"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"

settings = Settings()
