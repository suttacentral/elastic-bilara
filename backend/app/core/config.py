import secrets
from datetime import timedelta
from pathlib import Path
from typing import List, Union

from pydantic import AnyHttpUrl, BaseSettings, EmailStr, validator


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SERVER_NAME: str = "bilara-v2"
    SERVER_BACKEND_HOST: AnyHttpUrl = "http://localhost"
    DOCKER_BACKEND_PORT: str = "8080"
    PROJECT_NAME: str = "bilara-v2"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    WORK_DIR: Path = Path(__file__).parent.parent.parent / "checkouts" / "unpublished"
    PUBLISHED_DIR: Path = Path(__file__).parent.parent.parent / "checkouts" / "published"
    ELASTIC_USERNAME: str
    ELASTIC_PASSWORD: str
    ES_REQUESTS_PORT: int
    ES_URL: str
    ES_SCHEME: str
    ES_INDEX: str
    ES_SEGMENTS_INDEX: str
    ES_HOST: str
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: timedelta = timedelta(minutes=30)
    REFRESH_TOKEN_EXPIRE_DAYS: timedelta = timedelta(days=7)
    ALGORITHM: str = "HS256"
    USERS_FILE: Path = Path(__file__).parent.parent.parent / "users.json"
    GITHUB_ACCESS_TOKEN_URL: AnyHttpUrl = "https://github.com/login/oauth/access_token"
    GITHUB_USER_URL: AnyHttpUrl = "https://api.github.com/user"
    GITHUB_AUTHORIZE_URL: AnyHttpUrl = "https://github.com/login/oauth/authorize"
    GITHUB_ACCESS_SCOPES: str = "user:email"
    GITHUB_USERNAME: str
    GITHUB_EMAIL: EmailStr
    GITHUB_TOKEN: str
    GITHUB_REPO: str
    CELERY_BROKER_URL: str
    CELERY_BACKEND_URL: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
