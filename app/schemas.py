from pydantic import BaseModel, HttpUrl, field_validator

from app.config import settings


class ShortenRequest(BaseModel):
    long_url: HttpUrl

    @field_validator("long_url")
    @classmethod
    def enforce_max_length(cls, value: HttpUrl) -> HttpUrl:
        if len(str(value)) > settings.max_long_url_length:
            raise ValueError(
                f"long_url exceeds maximum length of {settings.max_long_url_length} characters"
            )
        return value


class ShortenResponse(BaseModel):
    short_code: str
    long_url: str
