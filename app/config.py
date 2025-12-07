from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://loanbot:loanbot@localhost:5432/loanbot"
    )
    llm_model: str = Field(default="llama3")
    llm_base_url: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None)
    allow_origins: list[str] = Field(default=["*"])

    class Config:
        env_prefix = "LOANBOT_"
        env_file = ".env"


settings = Settings()
