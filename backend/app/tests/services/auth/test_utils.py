from datetime import datetime, timedelta

import pytest
from app.core.config import settings
from app.services.auth.utils import create_jwt_token, set_auth_cookies
from fastapi import Response
from freezegun import freeze_time
from jose import JWTError, jwt


class TestAuthUtils:
    def test_auth_cookies_have_integer_max_age(self) -> None:
        response = Response()

        set_auth_cookies(response, "access", "refresh")

        cookie_headers = response.headers.getlist("set-cookie")
        access_max_age = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES.total_seconds())
        refresh_max_age = int(settings.REFRESH_TOKEN_EXPIRE_DAYS.total_seconds())
        assert any(f"Max-Age={access_max_age};" in header for header in cookie_headers)
        assert any(f"Max-Age={refresh_max_age};" in header for header in cookie_headers)

    @pytest.mark.parametrize(
        "token_type, exp",
        [
            ("access", settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            ("refresh", settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ],
    )
    @freeze_time(datetime.utcnow())
    def test_create_jwt_token(self, token_type, exp) -> None:
        data = {"sub": "123", "username": "test"}
        token = create_jwt_token(data=data, token_type=token_type)
        decoded_token = jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)

        expected_exp = datetime.utcnow() + exp
        assert decoded_token["sub"] == data["sub"]
        assert "exp" in decoded_token
        assert len(token.split(".")) == 3
        assert decoded_token["exp"] == int(expected_exp.timestamp())

    def test_create_unknown_token_type(self) -> None:
        data = {"sub": "123", "username": "test"}
        token_type = "invalid"
        with pytest.raises(Exception) as e:
            create_jwt_token(data=data, token_type=token_type)
        assert str(e.value) == f"Unknown token type {token_type}"

    @pytest.mark.parametrize(
        "token_type, exp",
        [
            ("access", settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            ("refresh", settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ],
    )
    @freeze_time(datetime.utcnow())
    def test_token_expiry(self, token_type, exp) -> None:
        data = {"sub": "123", "username": "test"}
        token = create_jwt_token(data=data, token_type=token_type)
        decoded_token = jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
        expected_exp = datetime.utcnow() + exp
        assert decoded_token["exp"] == int(expected_exp.timestamp())
        with freeze_time(datetime.utcnow() + exp + timedelta(seconds=1)):
            with pytest.raises(JWTError) as e:
                jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
            assert str(e.value) == "Signature has expired."
