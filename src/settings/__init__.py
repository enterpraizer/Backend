from pydantic import SecretStr
from pydantic_settings import BaseSettings

from src.settings.app import AppConfig
from src.settings.db import DatabaseConfig
from src.settings.email import EmailSettings
from src.settings.redis import RedisSettings


class Settings(BaseSettings):
    debug: bool = False
    app: AppConfig = AppConfig()
    db: DatabaseConfig = DatabaseConfig()
    email: EmailSettings = EmailSettings()
    redis: RedisSettings = RedisSettings()
    frontend_url: str
    secret_key: SecretStr


settings = Settings()
