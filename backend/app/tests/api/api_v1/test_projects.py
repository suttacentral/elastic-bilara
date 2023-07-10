from unittest.mock import patch

import pytest


class TestProjects:
    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.search.find_unique_data")
    async def test_get_projects(
        self,
        mock_find_unique_data,
        muids,
        async_client,
        mock_get_current_user,
    ) -> None:
        mock_find_unique_data.return_value = muids
        response = await async_client.get("/projects/")
        assert response.status_code == 200
        assert "projects" in response.json()
        assert len(response.json()["projects"]) == len(muids)
        assert response.json() == {"projects": muids}

    @pytest.mark.asyncio
    async def test_get_projects_unauthenticated(self, async_client) -> None:
        response = await async_client.get("/projects/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Not authenticated"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "prefix, expected_muids",
        [
            ("translation", ["translation-en-test", "translation-en-test2"]),
            ("nonexistent_prefix", []),
        ],
    )
    @patch("app.api.api_v1.endpoints.projects.search.find_unique_data")
    async def test_get_projects_with_prefix(
        self,
        mock_find_unique_data,
        muids,
        async_client,
        mock_get_current_user,
        prefix,
        expected_muids,
    ) -> None:
        filtered_muids = [muid for muid in muids if muid.startswith(prefix)]
        mock_find_unique_data.return_value = filtered_muids
        response = await async_client.get(f"/projects/?prefix={prefix}")
        assert response.status_code == 200
        assert "projects" in response.json()
        assert len(response.json()["projects"]) == len(filtered_muids)
        assert response.json() == {"projects": expected_muids}
        mock_find_unique_data.assert_called_once_with(field="muid", prefix=prefix)
