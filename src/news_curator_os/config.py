from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = "News Curator OS"
    app_db_path: str = Field(default="data/news_curator.db", alias="APP_DB_PATH")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_reload: bool = Field(default=True, alias="APP_RELOAD")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_organization: str | None = Field(default=None, alias="OPENAI_ORGANIZATION")
    default_language: str = Field(default="pt-BR", alias="DEFAULT_LANGUAGE")
    news_search_provider: str = Field(default="manual", alias="NEWS_SEARCH_PROVIDER")
    news_language: str = Field(default="pt", alias="NEWS_LANGUAGE")
    news_max_articles: int = Field(default=5, alias="NEWS_MAX_ARTICLES")
    newsapi_key: str | None = Field(default=None, alias="NEWSAPI_KEY")
    newsapi_base_url: str = Field(default="https://newsapi.org/v2/everything", alias="NEWSAPI_BASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
