from datetime import datetime, timedelta

from app.core.config import settings
from app.services.auth.schema import TokenData
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from starlette import status

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_jwt_token(*, data: dict, expires_delta: timedelta | None = None, token_type: str = "access") -> str:
    to_encode = data.copy()
    if expires_delta is None:
        if token_type == "access":
            expires_delta = timedelta(minutes=15)
        elif token_type == "refresh":
            expires_delta = timedelta(days=7)
        else:
            raise ValueError(f"Unknown token type {token_type}")
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    to_encode["sub"] = str(to_encode["sub"])
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
        github_id: str = payload.get("sub")
        username: str = payload.get("username")
        check_if_github_id_and_username_are_provided(github_id, username)
        token_data = TokenData(github_id=github_id, username=username)
    except JWTError:
        raise get_credentials_exception()
    return token_data


def get_credentials_exception():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def check_if_github_id_and_username_are_provided(github_id: str | None, username: str | None) -> None:
    if github_id is None or username is None:
        raise get_credentials_exception()
