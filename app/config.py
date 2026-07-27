from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./url_shortener.db"
    short_code_length: int = 7
    max_collision_retries: int = 5
    max_long_url_length: int = 2048


settings = Settings()
