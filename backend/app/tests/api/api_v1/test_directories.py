import json
from unittest.mock import patch

import pytest
from fastapi import status

from app.core.config import settings
from app.core.text_types import TextType
from app.services.directories.models import FilesAndDirsOut


class TestDirectories:
    @pytest.mark.asyncio
    async def test_translation_directory_supports_symlinked_work_directory(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        mocker,
        tmp_path,
    ):
        real_parent = tmp_path / "real-parent"
        logical_parent = tmp_path / "logical-parent"
        real_work_dir = real_parent / "unpublished"
        work_dir = logical_parent / "unpublished"
        source_dir = real_work_dir / "root/pli/ms/sutta/mn"
        target_dir = real_work_dir / "translation/en/tester/sutta/mn"
        source_dir.mkdir(parents=True)
        target_dir.mkdir(parents=True)
        (target_dir / "child").mkdir()
        (target_dir / "existing_translation-en-tester.json").write_text(
            json.dumps({"mn1:1.1": "Existing"}),
            encoding="utf-8",
        )
        (source_dir / "mn1_root-pli-ms.json").write_text(
            json.dumps({"mn1:1.1": "Source"}),
            encoding="utf-8",
        )
        (real_work_dir / "_project-v2.json").write_text(
            json.dumps(
                [
                    {
                        "root_path": "root/pli/ms/sutta",
                        "translation_path": "translation/en/tester/sutta",
                        "translation_muids": "translation-en-tester",
                    }
                ]
            ),
            encoding="utf-8",
        )
        logical_parent.symlink_to(real_parent, target_is_directory=True)
        monkeypatch.setattr(settings, "WORK_DIR", work_dir)
        mocker.patch(
            "app.api.api_v1.endpoints.directories.utils.calculate_file_progress",
            return_value={
                "name": "existing_translation-en-tester.json",
                "progress": 100,
                "total_keys": 1,
                "translated_keys": 1,
            },
        )

        response = await async_client.get(
            "/directories/translation/en/tester/sutta/mn/"
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["base"] == "translation/en/tester/sutta/mn/"
        assert body["directories"] == ["child/"]
        assert body["files"] == ["existing_translation-en-tester.json"]
        assert body["virtual_files"][0]["target_path"] == (
            "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
        )
        assert body["virtual_files"][0]["source_path"] == (
            "root/pli/ms/sutta/mn/mn1_root-pli-ms.json"
        )

    @pytest.mark.asyncio
    async def test_translation_directory_lists_missing_project_file_without_creating_it(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
    ):
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        target_dir = work_dir / "translation/en/tester/sutta/mn"
        source_dir.mkdir(parents=True)
        target_dir.mkdir(parents=True)
        source_file = source_dir / "mn1_root-pli-ms.json"
        source_file.write_text(json.dumps({"mn1:1.1": "Source"}), encoding="utf-8")
        (work_dir / "_project-v2.json").write_text(
            json.dumps(
                [
                    {
                        "project_uid": "en_ms_translation_tester",
                        "name": "Test translation",
                        "root_path": "root/pli/ms/sutta",
                        "translation_path": "translation/en/tester/sutta",
                        "translation_muids": "translation-en-tester",
                        "creator_github_handle": "tester",
                    }
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "WORK_DIR", work_dir)

        response = await async_client.get("/directories/translation/en/tester/sutta/mn/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["virtual_files"] == [
            {
                "name": "mn1_translation-en-tester.json",
                "target_path": "translation/en/tester/sutta/mn/mn1_translation-en-tester.json",
                "target_muid": "translation-en-tester",
                "source_path": "root/pli/ms/sutta/mn/mn1_root-pli-ms.json",
                "source_muid": "root-pli-ms",
                "prefix": "mn1",
            }
        ]
        assert not (target_dir / "mn1_translation-en-tester.json").exists()

    @pytest.mark.asyncio
    async def test_translation_directory_navigates_virtual_subdirectory(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
    ):
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        translation_root = work_dir / "translation/en/tester/sutta"
        source_dir.mkdir(parents=True)
        translation_root.mkdir(parents=True)
        (source_dir / "mn1_root-pli-ms.json").write_text(
            json.dumps({"mn1:1.1": "Source"}), encoding="utf-8"
        )
        (work_dir / "_project-v2.json").write_text(
            json.dumps(
                [
                    {
                        "root_path": "root/pli/ms/sutta",
                        "translation_path": "translation/en/tester/sutta",
                        "translation_muids": "translation-en-tester",
                    }
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "WORK_DIR", work_dir)

        root_response = await async_client.get("/directories/translation/en/tester/sutta/")
        nested_response = await async_client.get("/directories/translation/en/tester/sutta/mn/")

        assert root_response.status_code == status.HTTP_200_OK
        assert root_response.json()["virtual_directories"] == ["mn/"]
        assert nested_response.status_code == status.HTTP_200_OK
        assert [item["name"] for item in nested_response.json()["virtual_files"]] == [
            "mn1_translation-en-tester.json"
        ]
        assert not (translation_root / "mn").exists()

    @pytest.mark.asyncio
    async def test_translation_directory_rejects_conflicting_virtual_files(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
    ):
        work_dir = tmp_path / "unpublished"
        for root_path in ("root/pli/ms/sutta", "root/en/site/sutta"):
            source_dir = work_dir / root_path
            source_dir.mkdir(parents=True)
            (source_dir / "mn1_root-test.json").write_text(
                json.dumps({"mn1:1.1": "Source"}), encoding="utf-8"
            )
        target_dir = work_dir / "translation/en/tester/sutta"
        target_dir.mkdir(parents=True)
        (work_dir / "_project-v2.json").write_text(
            json.dumps(
                [
                    {
                        "root_path": "root/pli/ms/sutta",
                        "translation_path": "translation/en/tester/sutta",
                        "translation_muids": "translation-en-tester",
                    },
                    {
                        "root_path": "root/en/site/sutta",
                        "translation_path": "translation/en/tester/sutta",
                        "translation_muids": "translation-en-tester",
                    },
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "WORK_DIR", work_dir)

        response = await async_client.get("/directories/translation/en/tester/sutta/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Conflicting virtual translation file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_translation_directory_rejects_project_path_outside_work_directory(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
    ):
        work_dir = tmp_path / "unpublished"
        outside_dir = tmp_path / "outside"
        target_dir = work_dir / "translation/en/tester/sutta"
        outside_dir.mkdir()
        target_dir.mkdir(parents=True)
        (outside_dir / "mn1_root-test.json").write_text(
            json.dumps({"mn1:1.1": "Secret"}), encoding="utf-8"
        )
        (work_dir / "_project-v2.json").write_text(
            json.dumps(
                [
                    {
                        "root_path": "../outside",
                        "translation_path": "translation/en/tester/sutta",
                        "translation_muids": "translation-en-tester",
                    }
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "WORK_DIR", work_dir)

        response = await async_client.get("/directories/translation/en/tester/sutta/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "outside the work directory" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("pathlib.Path.iterdir")
    async def test_get_root_content(self, mock_iterdir, async_client, mock_get_current_user, mock_path_obj):
        mock_iterdir.return_value = [mock_path_obj(True, text_type.value) for text_type in TextType]
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
    @patch("pathlib.Path.is_dir", return_value=True)
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.iterdir")
    async def test_get_dir_content(self, mock_iterdir, mock_exists, mock_is_dir, async_client, mock_get_current_user, mock_path_obj):
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
