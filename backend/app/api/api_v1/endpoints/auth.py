from typing import Any

from app.core.config import settings
from app.services.auth import utils
from app.services.auth.models import AccessTokenOut, TokenOut
from app.services.auth.schema import RefreshToken
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

router = APIRouter()


@router.get("/login", status_code=status.HTTP_302_FOUND)
async def login() -> RedirectResponse:
    return RedirectResponse(
        url=f"{settings.GITHUB_AUTHORIZE_URL}?client_id={settings.GITHUB_CLIENT_ID}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/token", response_model=AccessTokenOut)
async def token(code: str) -> AccessTokenOut:
    data: dict[str, str] = await utils.get_github_data(code)
    if "error" in data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=data)

    token_data: dict[str, str] = {
        "sub": data["github_id"],
        "username": data["username"],
    }
    access_token: str = utils.create_jwt_token(
        data=token_data,
        expires_delta=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    refresh_token: str = utils.create_jwt_token(
        data=token_data,
        expires_delta=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        token_type="refresh",
    )
    return AccessTokenOut(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenOut)
async def refresh(refresh_token: RefreshToken) -> TokenOut:
    try:
        payload: dict[str, Any] = jwt.decode(refresh_token.refresh_token, settings.SECRET_KEY, settings.ALGORITHM)
        github_id: str = payload.get("sub")
        username: str = payload.get("username")
        utils.check_if_github_id_and_username_are_provided(github_id, username)
        new_access_token = utils.create_jwt_token(
            data={"sub": github_id, "username": username},
            expires_delta=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    except JWTError:
        raise utils.get_credentials_exception()
    return TokenOut(access_token=new_access_token)
