from unittest.mock import patch

import pytest
from celery import states


class TestTaskStatus:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mock_status, expected_status_code, expected_response",
        [
            (states.SUCCESS, 200, {"status": states.SUCCESS}),
            (states.PENDING, 200, {"status": states.PENDING}),
            (states.FAILURE, 200, {"status": states.FAILURE}),
        ],
    )
    @patch("app.api.api_v1.endpoints.tasks.app.AsyncResult")
    async def test_get_task_status(
        self,
        mock_async_result,
        mock_status,
        expected_status_code,
        expected_response,
        async_client,
        mock_get_current_user,
    ):
        task_id = "test_task_id"
        mock_instance = mock_async_result.return_value
        mock_instance.status = mock_status

        response = await async_client.get(f"/tasks/{task_id}/")
        assert response.status_code == expected_status_code
        assert response.json() == expected_response

    @pytest.mark.asyncio
    async def test_get_task_status_unauthenticated(self, async_client):
        task_id = "test_task_id"
        response = await async_client.get(f"/tasks/{task_id}/")
        assert response.status_code == 401
        assert response.json() == {"detail": "Could not validate credentials"}
