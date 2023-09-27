from typing import Any

from app.core.config import settings
from app.services.auth import utils
from app.services.auth.models import AccessTokenOut, TokenOut
from fastapi import APIRouter, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

router = APIRouter()


@router.get("/login/", status_code=status.HTTP_302_FOUND)
async def login() -> RedirectResponse:
    return RedirectResponse(
        url=f"{settings.GITHUB_AUTHORIZE_URL}?client_id={settings.GITHUB_CLIENT_ID}&scope={settings.GITHUB_ACCESS_SCOPES}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/token/", response_model=AccessTokenOut)
async def token(response: Response, code: str) -> AccessTokenOut:
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
    utils.set_auth_cookies(response, access_token, refresh_token)
    return AccessTokenOut(access_token="Token stored in cookies", refresh_token="Token stored in cookies")


@router.post("/refresh/", response_model=TokenOut)
async def refresh(request: Request, response: Response) -> TokenOut:
    raw_refresh_token = request.cookies.get("refresh_token")
    if not raw_refresh_token:
        raise utils.get_credentials_exception()
    try:
        payload: dict[str, Any] = jwt.decode(raw_refresh_token, settings.SECRET_KEY, settings.ALGORITHM)
        github_id: str = payload.get("sub")
        username: str = payload.get("username")
        utils.check_if_github_id_and_username_are_provided(github_id, username)
        new_access_token = utils.create_jwt_token(
            data={"sub": github_id, "username": username},
            expires_delta=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
        utils.set_auth_cookies(response, new_access_token)
    except JWTError:
        raise utils.get_credentials_exception()
    return TokenOut(access_token="Token stored in cookies")


@router.post("/logout/", status_code=status.HTTP_200_OK)
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"detail": "Successfully logged out"}
