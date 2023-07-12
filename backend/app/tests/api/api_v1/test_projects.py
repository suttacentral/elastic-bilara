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

    @pytest.mark.asyncio
    async def test_get_root_paths_for_project_unauthenticated(self, async_client) -> None:
        response = await async_client.get("/projects/translation-en-test/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Not authenticated"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_get_root_paths_for_project(self, mock_get_file_paths, async_client, mock_get_current_user) -> None:
        mock_get_file_paths.return_value = ["root/path1", "root/path2"]
        response = await async_client.get("/projects/translation-en-test/")
        assert response.status_code == 200
        assert "root_paths" in response.json()
        assert len(response.json()["root_paths"]) == 2
        assert response.json() == {"root_paths": ["root/path1", "root/path2"]}
        mock_get_file_paths.assert_called_once_with(muid="translation-en-test")

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_get_root_paths_for_project_muid_does_not_exist(
        self, mock_get_file_paths, async_client, mock_get_current_user
    ) -> None:
        mock_get_file_paths.return_value = []
        response = await async_client.get("/projects/nonexistent_muid/")
        assert response.status_code == 404
        assert "detail" in response.json()
        assert response.json() == {"detail": "Project 'nonexistent_muid' not found"}
