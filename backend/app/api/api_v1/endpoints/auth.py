from typing import Any

import httpx
from app.core.config import settings
from app.services.auth.schema import RefreshToken
from app.services.auth.utils import (
    check_if_github_id_and_username_are_provided,
    create_jwt_token,
    get_credentials_exception,
)
from app.services.users.populate_data import add_user_to_users_json
from fastapi import APIRouter
from httpx import HTTPStatusError, Response
from jose import JWTError, jwt
from starlette.responses import RedirectResponse

router = APIRouter()


@router.get("/login")
async def login() -> RedirectResponse:
    return RedirectResponse(
        url=f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}",
        status_code=302,
    )


@router.get("/auth")
async def auth(code: str) -> dict[str, str]:
    params: dict[str, str] = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }
    headers: dict[str, str] = {"Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        try:
            response: Response = await client.post(
                url="https://github.com/login/oauth/access_token",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data: dict = response.json()
            token_type: str = data.get("token_type")
            access_token: str = data.get("access_token")
            headers.update({"Authorization": f"{token_type} {access_token}"})
            response: Response = await client.get("https://api.github.com/user", headers=headers)
            response.raise_for_status()
            user_data: dict = response.json()
            data = {
                "github_id": user_data.get("id"),
                "username": user_data.get("login"),
                "email": user_data.get("email"),
                "avatar_url": user_data.get("avatar_url"),
            }
        except HTTPStatusError as e:
            return {"error": str(e)}
    add_user_to_users_json(data)
    return data


@router.get("/token")
async def token(code: str) -> dict[str, str]:
    data: dict[str, str] = await auth(code)
    if "error" in data:
        return data

    token_data: dict[str, str] = {
        "sub": data["github_id"],
        "username": data["username"],
    }
    access_token: str = create_jwt_token(
        data=token_data,
        expires_delta=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    refresh_token: str = create_jwt_token(
        data=token_data,
        expires_delta=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        token_type="refresh",
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh(refresh_token: RefreshToken) -> dict[str, str]:
    try:
        payload: dict[str, Any] = jwt.decode(refresh_token.refresh_token, settings.SECRET_KEY, settings.ALGORITHM)
        github_id: str = payload.get("sub")
        username: str = payload.get("username")
        check_if_github_id_and_username_are_provided(github_id, username)
        new_access_token = create_jwt_token(
            data={"sub": github_id, "username": username},
            expires_delta=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    except JWTError:
        raise get_credentials_exception()
    return {"access_token": new_access_token, "token_type": "bearer"}
