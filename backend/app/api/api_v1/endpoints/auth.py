from typing import Any

from app.core.config import settings
from app.services.auth.schema import RefreshToken
from app.services.auth.utils import (
    check_if_github_id_and_username_are_provided,
    create_jwt_token,
    get_credentials_exception,
    get_github_data,
)
from app.services.users.permissions import can_edit_translation
from fastapi import APIRouter
from jose import JWTError, jwt
from starlette.responses import RedirectResponse

router = APIRouter()


@router.get("/login")
async def login() -> RedirectResponse:
    return RedirectResponse(
        url=f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}",
        status_code=302,
    )


@router.get("/token")
async def token(code: str) -> dict[str, str]:
    data: dict[str, str] = await get_github_data(code)
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
