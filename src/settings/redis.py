from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="redis_",
        extra="ignore"
    )

    host: str
    port: int
    db: int

    @property
    def url(self):
        return f"redis://{self.host}:{self.port}/{self.db}"
