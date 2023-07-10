from pydantic import BaseModel


class TokenData(BaseModel):
    github_id: str | None = None
    username: str | None = None


class RefreshToken(BaseModel):
    refresh_token: str
    github_id: str | None = None
    username: str | None = None
