from unittest.mock import patch

import pytest
from fastapi import status

from app.core.text_types import TextType
from app.services.directories.models import FilesAndDirsOut


class TestDirectories:
    @pytest.mark.asyncio
    async def test_get_root_content(self, async_client, mock_get_current_user):
        response = await async_client.get("/directories/")
        assert response.status_code == status.HTTP_200_OK
        assert FilesAndDirsOut(**response.json())
        assert all([f"{text_type.value}/" in response.json()["directories"] for text_type in TextType])

    @pytest.mark.asyncio
    async def test_get_root_content_unauthorized(self, async_client):
        response = await async_client.get("/directories/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()
        assert response.json()["detail"] == "Could not validate credentials"

    @pytest.mark.asyncio
    @patch("pathlib.Path.iterdir")
    async def test_get_dir_content(self, mock_iterdir, async_client, mock_get_current_user, mock_path_obj):
        mock_iterdir.return_value = [
            mock_path_obj(True, "dir1"),
            mock_path_obj(True, "dir2"),
            mock_path_obj(False, "file1"),
            mock_path_obj(False, "file2"),
        ]
        for text_type in TextType:
            response = await async_client.get(f"/directories/{text_type.value}/")
            assert response.status_code == status.HTTP_200_OK
            assert FilesAndDirsOut(**response.json())
            assert response.json()["base"] == f"{text_type.value}/"
            assert all(item in response.json()["directories"] for item in {"dir1/", "dir2/"})
            assert all(item in response.json()["files"] for item in {"file1", "file2"})

    @pytest.mark.asyncio
    async def test_get_dir_content_invalid_path(self, async_client, mock_get_current_user):
        invalid_directory = "invalid_path"
        response = await async_client.get(f"/directories/{invalid_directory}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in response.json()
        assert response.json()["detail"] == f"Path {invalid_directory} not found"

    @pytest.mark.asyncio
    async def test_get_dir_content_unauthorized(self, async_client):
        response = await async_client.get(f"/directories/{TextType.ROOT.value}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()
        assert response.json()["detail"] == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_delete_path_unauthorized(self, async_client):
        response = await async_client.delete(
            "/directories/translation/en/test/sutta/test/test1/", params={"dry_run": True}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()
        assert response.json()["detail"] == "Could not validate credentials"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.directories.can_delete_projects")
    async def test_delete_path_user_writer(
        self,
        mock_can_delete_projects,
        async_client,
        mock_validate_path,
        mock_get_current_user,
    ):
        mock_can_delete_projects.return_value = False
        response = await async_client.delete(
            "/directories/translation/en/test/sutta/test/test1/", params={"dry_run": True}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "detail" in response.json()
        assert response.json()["detail"] == "You are not allowed to delete projects"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.directories.Remover")
    @patch("app.api.api_v1.endpoints.directories.can_delete_projects")
    async def test_delete_path_dry_run(
        self,
        mock_can_delete_projects,
        mock_remover,
        async_client,
        mock_validate_path,
        mock_get_current_user_admin,
    ):
        remover_instance = mock_remover.return_value
        root_path_str = "/root/pli/ms/sutta/test/test1/"
        translation_path_str = "/translation/en/test/sutta/test/test1/"
        remover_instance.delete_dry.return_value = [root_path_str, translation_path_str]
        mock_can_delete_projects.return_value = True
        response = await async_client.delete(f"/directories/{translation_path_str}", params={"dry_run": True})
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.json()
        assert "results" in response.json()
        assert response.json()["message"] == "Dry run successful"
        assert root_path_str in response.json()["results"][0]["path"]
        assert translation_path_str in response.json()["results"][1]["path"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.directories.Remover")
    @patch("app.api.api_v1.endpoints.directories.can_delete_projects")
    async def test_delete_path(
        self,
        mock_can_delete_projects,
        mock_remover,
        async_client,
        mock_validate_path,
        mock_get_current_user_admin,
    ):
        remover_instance = mock_remover.return_value
        main_path_task_id = "main"
        related_paths_task_id = "related"
        remover_instance.delete.return_value = (main_path_task_id, related_paths_task_id)
        mock_can_delete_projects.return_value = True
        response = await async_client.delete(
            f"/directories/translation/en/test/sutta/test/test1/", params={"dry_run": False}
        )
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.json()
        assert "main_task_id" in response.json()
        assert "related_paths_task_id" in response.json()
        assert response.json()["message"] == "Deletion successful"
        assert response.json()["main_task_id"] == main_path_task_id
        assert response.json()["related_paths_task_id"] == related_paths_task_id
