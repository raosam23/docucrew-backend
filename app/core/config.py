from pydantic_settings import SettingsConfigDict
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "DocuCrew"
    APP_ENV: str
    DEBUG: bool

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SALT_ROUNDS: int = 12

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    CHROMA_PERSIST_DIR: str = "./chroma_data"

    REDIS_URL: str = "redis://localhost:6379"

    TAVILY_API_KEY: str

    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()