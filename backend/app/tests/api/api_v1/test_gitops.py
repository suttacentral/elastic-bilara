import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import settings


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(async_client):
    response = await async_client.post(
        "/git/sync",
        headers={"x-hub-signature-256": "sha256=1234", "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid signature"}


@pytest.mark.asyncio
async def test_github_webhook_invalid_branch(async_client):
    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    payload = {"pull_request": {"base": {"ref": "refs/heads/invalid"}}}
    payload_bytes = json.dumps(payload).encode("utf-8")

    signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
    response = await async_client.post(
        "/git/sync",
        headers={"x-hub-signature-256": f"sha256={signature}", "Content-Type": "application/x-www-form-urlencoded"},
        json={"pull_request": {"base": {"ref": "refs/heads/invalid"}}},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid branch name. Use 'published' or 'unpublished'"}


@pytest.mark.asyncio
async def test_github_webhook_valid_branch(async_client, mock_users):
    with patch("app.api.api_v1.endpoints.git_ops.hmac.compare_digest", return_value=True):
        with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_users[0]):
            with patch("app.api.api_v1.endpoints.git_ops.pull.delay", return_value=MagicMock(id="123456")):
                with patch("app.api.api_v1.endpoints.git_ops.push.delay", return_value=MagicMock(id="654321")):
                    response = await async_client.post(
                        "/git/sync",
                        headers={
                            "x-hub-signature-256": f"sha256={settings.GITHUB_WEBHOOK_SECRET.encode()}}}",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                        json={"pull_request": {"base": {"ref": "refs/heads/published"}}, "sender": {"id": 123456}},
                    )
                    assert response.status_code == 201
                    assert response.json() == {
                        "detail": "Sync action has been triggered",
                        "task_id": ["123456", "654321"],
                    }


@pytest.mark.asyncio
async def test_sync_repository_data_unauthorized(async_client):
    response = await async_client.get("/git/sync/published")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_repository_data_invalid_branch(
    async_client, mock_get_current_user, mock_is_admin_or_superuser_is_active, mock_users
):
    mock_users[0].role = "administrator"
    with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_users[0]):
        response = await async_client.get("/git/sync/invalid")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid branch name. Use 'published' or 'unpublished'"}


@pytest.mark.asyncio
async def test_sync_repository_data_valid_branch(
    async_client, mock_get_current_user, mock_is_admin_or_superuser_is_active, mock_users
):
    mock_users[0].role = "administrator"
    with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_users[0]):
        with patch("app.api.api_v1.endpoints.git_ops.pull.delay", return_value=MagicMock(id="123456")):
            with patch("app.api.api_v1.endpoints.git_ops.push.delay", return_value=MagicMock(id="654321")):
                response = await async_client.get("/git/sync/published")

                assert response.status_code == 201
                assert response.json() == {"detail": "Sync action has been triggered", "task_id": ["123456", "654321"]}
