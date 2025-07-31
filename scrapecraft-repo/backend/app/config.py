from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    OPENROUTER_API_KEY: str
    SCRAPEGRAPH_API_KEY: str
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:80"]
    
    # OpenRouter Config
    OPENROUTER_MODEL: str = "moonshotai/kimi-k2"
    
    # App Config
    APP_NAME: str = "ScrapeCraft"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()