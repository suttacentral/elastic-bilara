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
