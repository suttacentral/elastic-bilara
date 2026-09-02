from pathlib import Path
from unittest.mock import patch

import pytest
from celery import states


class TestTaskStatus:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mock_status, ready, info, result, expected_status_code, expected_response",
        [
            (states.SUCCESS, True, None, {"status": "success"}, 200, {"status": states.SUCCESS, "result": {"status": "success"}}),
            (states.PENDING, False, None, None, 200, {"status": states.PENDING}),
            ("PROGRESS", False, {"current": 2, "total": 5}, None, 200, {"status": "PROGRESS", "info": {"current": 2, "total": 5}}),
            (states.FAILURE, True, None, RuntimeError("boom"), 200, {"status": states.FAILURE, "error": "boom"}),
        ],
    )
    @patch("app.api.api_v1.endpoints.tasks.app.AsyncResult")
    async def test_get_task_status(
        self,
        mock_async_result,
        mock_status,
        ready,
        info,
        result,
        expected_status_code,
        expected_response,
        async_client,
        mock_get_current_user,
    ):
        task_id = "test_task_id"
        mock_instance = mock_async_result.return_value
        mock_instance.status = mock_status
        mock_instance.ready.return_value = ready
        mock_instance.info = info
        mock_instance.result = result

        response = await async_client.get(f"/tasks/{task_id}/")
        assert response.status_code == expected_status_code
        assert response.json() == expected_response

    @pytest.mark.asyncio
    async def test_get_task_status_unauthenticated(self, async_client):
        task_id = "test_task_id"
        response = await async_client.get(f"/tasks/{task_id}/")
        assert response.status_code == 401
        assert response.json() == {"detail": "Could not validate credentials"}


@patch("app.tasks.GitManager")
def test_pull_request_task_delegates_all_paths_to_bounded_publication(mock_git_manager, user):
    from app.tasks import pr

    paths = [
        "/app/checkouts/unpublished/translations/en/test/sutta/an/an1/an1.1.json",
        "/app/checkouts/unpublished/translations/en/test/sutta/an/an1/an1.2.json",
    ]
    manager = mock_git_manager.return_value
    mock_git_manager.add.return_value = False
    manager.publish_files.return_value = "https://github.com/example/pull/1"

    result = pr(user.model_dump(), paths)

    assert result == "https://github.com/example/pull/1"
    manager.publish_files.assert_called_once_with(
        [
            Path("translations/en/test/sutta/an/an1/an1.1.json"),
            Path("translations/en/test/sutta/an/an1/an1.2.json"),
        ]
    )
