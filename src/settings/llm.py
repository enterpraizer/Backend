from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore"
    )

    gemini_api_key: str = ""
    model: str = "gemini-flash-lite-latest"
    enabled: bool = True
