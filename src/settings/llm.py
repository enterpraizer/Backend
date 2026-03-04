from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    model: str = "claude-3-haiku-20240307"
    enabled: bool = True
