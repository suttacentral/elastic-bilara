from unittest.mock import patch

import pytest
from app.core.config import settings
from app.services.auth.schema import RefreshToken


class TestAuth:
    @pytest.mark.asyncio
    async def test_login_endpoint(self, async_client) -> None:
        response = await async_client.get("/login/")
        assert response.status_code == 302
        assert (
            response.headers["location"]
            == f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&scope={settings.GITHUB_ACCESS_SCOPES}"
        )

    @pytest.mark.asyncio
    async def test_token_endpoint_invalid_code(self, async_client) -> None:
        response = await async_client.get("/token/?code=invalid_code")
        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.auth.utils.create_jwt_token")
    @patch("app.api.api_v1.endpoints.auth.utils.get_github_data")
    async def test_token_endpoint_valid_code(
        self, mock_get_github_data, mock_create_jwt_token, github_data, async_client
    ) -> None:
        token = "valid_token"
        mock_get_github_data.return_value = github_data()
        mock_create_jwt_token.return_value = token
        response = await async_client.get("/token/?code=valid_code")
        assert response.status_code == 200
        assert response.json() == {
            "access_token": token,
            "refresh_token": token,
            "token_type": "bearer",
        }

    @pytest.mark.asyncio
    async def test_refresh_endpoint_invalid_token(self, async_client) -> None:
        response = await async_client.post("/refresh/", json={"refresh_token": "invalid"})
        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_refresh_endpoint_token_not_provided(self, async_client) -> None:
        response = await async_client.post("/refresh/")
        assert response.status_code == 422
        assert "detail" in response.json()

    @pytest.mark.asyncio
    @patch("jose.jwt.decode")
    @patch("app.api.api_v1.endpoints.auth.utils.create_jwt_token")
    async def test_refresh_endpoint_valid_token(self, mock_create_jwt_token, mock_jwt_decode, async_client) -> None:
        mock_refresh_token_data = {"refresh_token": "mock_refresh_token"}
        mock_refresh_token = RefreshToken(**mock_refresh_token_data)

        mock_payload = {"sub": "mock_id", "username": "mock_username"}
        mock_jwt_decode.return_value = mock_payload

        mock_new_access_token = "mock_new_access_token"
        mock_create_jwt_token.return_value = mock_new_access_token

        response = await async_client.post("/refresh/", json=mock_refresh_token.dict())

        assert response.status_code == 200
        assert response.json() == {
            "access_token": mock_new_access_token,
            "token_type": "bearer",
        }
