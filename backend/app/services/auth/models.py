from pydantic import BaseModel


class TokenOut(BaseModel):
    token_type: str = "bearer"
    access_token: str


class AccessTokenOut(TokenOut):
    refresh_token: str
