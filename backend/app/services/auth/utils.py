from datetime import datetime, timedelta

import httpx
from app.core.config import settings
from app.services.auth.schema import TokenData
from app.services.users.utils import add_user_to_db
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from httpx import HTTPStatusError, Response
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_jwt_token(*, data: dict, expires_delta: timedelta | None = None, token_type: str = "access") -> str:
    to_encode = data.copy()
    if expires_delta is None:
        if token_type == "access":
            expires_delta = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        elif token_type == "refresh":
            expires_delta = settings.REFRESH_TOKEN_EXPIRE_DAYS
        else:
            raise ValueError(f"Unknown token type {token_type}")
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    to_encode["sub"] = str(to_encode["sub"])
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
        github_id: str = payload.get("sub")
        username: str = payload.get("username")
        check_if_github_id_and_username_are_provided(github_id, username)
        token_data = TokenData(github_id=github_id, username=username)
    except JWTError:
        raise get_credentials_exception()
    return token_data


def get_credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def check_if_github_id_and_username_are_provided(github_id: str | None, username: str | None) -> None:
    if github_id is None or username is None:
        raise get_credentials_exception()


async def get_github_data(code: str) -> dict[str, str | int]:
    params: dict[str, str] = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }
    headers: dict[str, str] = {"Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        try:
            response: Response = await client.post(
                url=settings.GITHUB_ACCESS_TOKEN_URL,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data: dict = response.json()
            token_type: str = data.get("token_type")
            access_token: str = data.get("access_token")
            headers.update({"Authorization": f"{token_type} {access_token}"})
            response: Response = await client.get(settings.GITHUB_USER_URL, headers=headers)
            response.raise_for_status()
            user_data: dict = response.json()
            if not (email := user_data.get("email")):
                email_data_response: Response = await client.get(settings.GITHUB_USER_URL + "/emails", headers=headers)
                email_data_response.raise_for_status()
                email: str = [item["email"] for item in email_data_response.json() if item.get("primary")][0]
            data = {
                "github_id": user_data.get("id"),
                "username": user_data.get("login"),
                "email": email,
                "avatar_url": user_data.get("avatar_url"),
            }
        except HTTPStatusError as e:
            return {"error": str(e)}
    add_user_to_db(data)
    return data
