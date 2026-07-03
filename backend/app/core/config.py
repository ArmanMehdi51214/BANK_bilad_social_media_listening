from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Bank Albilad Executive Social Media Intelligence"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "bank_albilad_social_intelligence"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"

    SECRET_KEY: str = "change-this-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    LOG_LEVEL: str = "INFO"

    # X / Twitter data provider
    X_DATA_PROVIDER: str = "apify"

    # Apify X/Twitter scraper configuration
    APIFY_API_TOKEN: str = ""
    APIFY_X_ACTOR_ID: str = "apidojo/tweet-scraper"
    APIFY_BASE_URL: str = "https://api.apify.com/v2"
    APIFY_MAX_TWEETS_PER_RUN: int = 50
    APIFY_RUN_TIMEOUT_SECONDS: int = 180

    X_BEARER_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def apify_actor_path(self) -> str:
        """
        Apify actor URL path uses ~ instead of /.
        Example: apidojo/tweet-scraper -> apidojo~tweet-scraper
        """
        return self.APIFY_X_ACTOR_ID.replace("/", "~")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
