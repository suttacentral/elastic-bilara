from unittest.mock import patch

import pytest


class TestPullRequest:
    @pytest.mark.asyncio
    async def test_create_pull_request_unauthenticated(self, async_client):
        payload = {"paths": ["/path1", "/path2"]}
        response = await async_client.post("/pr/", json=payload)
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Not authenticated"}

    @pytest.mark.asyncio
    async def test_create_pull_request_empty_paths(self, mock_get_current_user, async_client):
        payload = {"paths": []}
        response = await async_client.post("/pr/", json=payload)
        assert response.status_code == 422
        assert "detail" in response.json()
        assert response.json() == {
            "detail": [
                {
                    "input": [],
                    "loc": ["body", "paths"],
                    "msg": "List should have at least 1 item after validation, not 0",
                    "type": "too_short",
                    "url": "https://errors.pydantic.dev/2.3/v/too_short",
                    "ctx": {"field_type": "List", "min_length": 1, "actual_length": 0},
                }
            ]
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "paths, is_consistent, expected_status, expected_response",
        [
            (
                [
                    "/app/checkouts/unpublished/translation/en/test/sutta/an/an1/an1.1-10_translation-en-test.json",
                ],
                True,
                201,
                {"detail": "Pull request creation has been scheduled", "task_id": "test_task_id"},
            ),
            (
                [
                    "/app/checkouts/unpublished/translation/en/test/sutta/an/an1/an1.1-10_translation-en-test.json",
                    "/app/checkouts/unpublished/translation/en/test/sutta/an/an1/an1.11-20_translation-en-test.json",
                ],
                True,
                201,
                {"detail": "Pull request creation has been scheduled", "task_id": "test_task_id"},
            ),
            (
                [
                    "/app/checkouts/unpublished/translation/en/test/sutta/an/an1/an1.1-10_translation-en-test.json",
                    "/app/checkouts/unpublished/translation/fr/test/sutta/sn/sn1/sn1.1-10_translation-fr-test.json",
                ],
                False,
                400,
                {
                    "detail": {
                        "error": "Paths must belong to the same project",
                        "mismatched_paths": ["/translation/fr/test/sutta/sn/sn1/sn1.1-10_translation-fr-test.json"],
                    }
                },
            ),
        ],
    )
    @patch("app.api.api_v1.endpoints.pull_request.pr")
    @patch("app.api.api_v1.endpoints.pull_request.get_user")
    async def test_create_pull_request(
        self,
        mock_get_user,
        mock_pr,
        paths,
        is_consistent,
        expected_status,
        expected_response,
        mock_get_current_user,
        async_client,
        user,
    ):
        mock_get_user.return_value = user
        if is_consistent:
            mock_pr.delay.return_value.id = "test_task_id"
        response = await async_client.post("/pr/", json={"paths": paths})
        assert response.status_code == expected_status
        assert response.json() == expected_response
        if is_consistent:
            mock_pr.delay.assert_called_once_with(user.model_dump(), paths)
