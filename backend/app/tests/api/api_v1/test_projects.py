from copy import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.config import settings
from app.services.projects.utils import OverrideException
from elasticsearch import RequestError
from fastapi import HTTPException, status


def _virtual_source_paths(source_path: Path):
    def get_file_paths(muid: str, **_kwargs) -> set[str]:
        return {str(source_path)} if muid == "root-pli-ms" else set()

    return get_file_paths


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
        assert response.json() == {"detail": "Could not validate credentials"}

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
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "muid, prefix, _type",
        [
            ("translation-en-test", None, "root_path"),
            ("translation-en-test", None, "file_path"),
            ("translation-en-test", "an", "root_path"),
            ("translation-en-test", "sn", "file_path"),
        ],
    )
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_get_paths_for_project(
        self, mock_get_file_paths, muid, prefix, _type, async_client, mock_get_current_user
    ):
        mock_get_file_paths.return_value = {"root/path1", "root/path2"}

        url = f"/projects/{muid}/"
        if prefix:
            url += f"?prefix={prefix}"
        if _type:
            url += f"{'?' if not prefix else '&'}_type={_type}"

        response = await async_client.get(url)

        assert response.status_code == 200
        assert "paths" in response.json()
        assert len(response.json()["paths"]) == 2
        assert response.json() == {"paths": ["root/path1", "root/path2"]}
        mock_get_file_paths.assert_called_once_with(muid=muid, _type=_type, prefix=prefix)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("_type", ["root_path", "file_path"])
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_get_paths_for_project_muid_does_not_exist(
        self, mock_get_file_paths, _type, async_client, mock_get_current_user
    ) -> None:
        mock_get_file_paths.return_value = set()

        url = f"/projects/nonexistent_muid/?_type={_type}"
        response = await async_client.get(url)

        assert response.status_code == 404
        assert "detail" in response.json()
        assert response.json() == {"detail": "Project 'nonexistent_muid' not found"}

    @pytest.mark.asyncio
    async def test_get_json_data_for_prefix_in_project_unauthenticated(self, async_client) -> None:
        response = await async_client.get("/projects/translation-en-test/an1.1-10/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation", return_value=True)
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths", return_value=set())
    async def test_get_virtual_translation_without_creating_file(
        self,
        _mock_get_file_paths,
        _mock_can_edit,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
    ) -> None:
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "mn1_root-pli-ms.json"
        source_file.write_text(json.dumps({"mn1:1.1": "Source"}), encoding="utf-8")
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
        _mock_get_file_paths.side_effect = _virtual_source_paths(source_file)
        target_file = (
            work_dir / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
        )

        response = await async_client.get("/projects/translation-en-tester/mn1/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "can_edit": True,
            "data": {},
            "task_id": None,
            "materialized": False,
            "structure_revision": hashlib.sha256(b'[["mn1:1.1"],null]').hexdigest(),
        }
        assert not target_file.exists()

    @pytest.mark.asyncio
    async def test_first_virtual_translation_save_writes_every_root_key(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
        mocker,
        user,
    ) -> None:
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "mn1_root-pli-ms.json"
        source_file.write_text(
            json.dumps(
                {
                    "mn1:1.1": "First source",
                    "mn1:1.2": "Second source",
                    "mn1:1.3": "Third source",
                }
            ),
            encoding="utf-8",
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
        mocker.patch(
            "app.api.api_v1.endpoints.projects.search.get_file_paths",
            side_effect=_virtual_source_paths(source_file),
        )
        mocker.patch(
            "app.api.api_v1.endpoints.projects.can_edit_translation", return_value=True
        )
        mocker.patch("app.services.projects.utils.get_user", return_value=user)
        mocker.patch(
            "app.services.projects.utils.search.add_to_index", return_value=(True, None)
        )
        commit_result = mocker.Mock(id="materialize-task")
        mocker.patch("app.services.projects.utils.commit.delay", return_value=commit_result)
        mocker.patch("app.tasks.update_file_translation_progress.delay")
        target_file = (
            work_dir / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
        )

        response = await async_client.patch(
            "/projects/translation-en-tester/mn1/",
            json={"mn1:1.2": "译文"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "can_edit": True,
            "data": {"mn1:1.2": "译文"},
            "task_id": "materialize-task",
            "materialized": True,
            "structure_revision": None,
        }
        assert json.loads(target_file.read_text(encoding="utf-8")) == {
            "mn1:1.1": "",
            "mn1:1.2": "译文",
            "mn1:1.3": "",
        }

    @pytest.mark.asyncio
    async def test_empty_first_virtual_translation_save_does_not_create_file(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
        mocker,
    ) -> None:
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "mn1_root-pli-ms.json"
        source_file.write_text(
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
        mocker.patch(
            "app.api.api_v1.endpoints.projects.search.get_file_paths",
            side_effect=_virtual_source_paths(source_file),
        )
        mocker.patch(
            "app.api.api_v1.endpoints.projects.can_edit_translation", return_value=True
        )
        target_file = (
            work_dir / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
        )

        response = await async_client.patch(
            "/projects/translation-en-tester/mn1/",
            json={"mn1:1.1": "   "},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["materialized"] is False
        assert response.json()["task_id"] is None
        assert not target_file.exists()

    @pytest.mark.asyncio
    async def test_first_virtual_translation_save_rolls_back_when_indexing_fails(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
        mocker,
    ) -> None:
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "mn1_root-pli-ms.json"
        source_file.write_text(
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
        mocker.patch(
            "app.api.api_v1.endpoints.projects.search.get_file_paths",
            side_effect=_virtual_source_paths(source_file),
        )
        mocker.patch(
            "app.api.api_v1.endpoints.projects.can_edit_translation", return_value=True
        )
        mocker.patch(
            "app.services.projects.utils.search.add_to_index",
            return_value=(False, RuntimeError("index unavailable")),
        )
        mocker.patch(
            "app.services.projects.utils.search.remove_segments", return_value=(True, None)
        )
        target_file = (
            work_dir / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
        )

        response = await async_client.patch(
            "/projects/translation-en-tester/mn1/",
            json={"mn1:1.1": "Translation"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "index unavailable"
        assert not target_file.exists()

    @pytest.mark.asyncio
    async def test_first_virtual_translation_save_rejects_unknown_root_key(
        self,
        async_client,
        mock_get_current_user,
        monkeypatch,
        tmp_path,
        mocker,
    ) -> None:
        work_dir = tmp_path / "unpublished"
        source_dir = work_dir / "root/pli/ms/sutta/mn"
        source_dir.mkdir(parents=True)
        source_file = source_dir / "mn1_root-pli-ms.json"
        source_file.write_text(
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
        mocker.patch(
            "app.api.api_v1.endpoints.projects.search.get_file_paths",
            side_effect=_virtual_source_paths(source_file),
        )
        mocker.patch(
            "app.api.api_v1.endpoints.projects.can_edit_translation", return_value=True
        )
        target_file = (
            work_dir / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
        )

        response = await async_client.patch(
            "/projects/translation-en-tester/mn1/",
            json={"mn1:9.9": "Invalid"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "mn1:9.9 not found in the root file" in response.json()["detail"]
        assert not target_file.exists()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_get_json_data_for_prefix_in_project_invalid_prefix(
        self, mock_get_file_paths, async_client, mock_get_current_user
    ) -> None:
        mock_get_file_paths.return_value = set()
        response = await async_client.get("/projects/translation-en-test/nonexistent_prefix/")
        assert response.status_code == 404
        assert "detail" in response.json()
        assert response.json() == {
            "detail": "Data for project 'translation-en-test' and prefix 'nonexistent_prefix' not found"
        }

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.search.add_to_index")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    async def test_get_json_data_for_prefix_in_project_discovers_unindexed_project_file(
        self,
        mock_can_edit_translation,
        mock_get_file_paths,
        mock_add_to_index,
        async_client,
        mock_get_current_user,
        tmp_path,
        monkeypatch,
    ) -> None:
        work_dir = tmp_path / "unpublished"
        file_path = work_dir / "translation/zh/blurb/an-blurbs_translation-zh.json"
        root_path = work_dir / "root/pli/ms/an-blurbs_root-pli-ms.json"
        file_path.parent.mkdir(parents=True)
        root_path.parent.mkdir(parents=True)
        file_path.write_text(json.dumps({"an1:0.1": "Test"}), encoding="utf-8")
        root_path.write_text(json.dumps({"an1:0.1": "Source"}), encoding="utf-8")
        monkeypatch.setattr(settings, "WORK_DIR", work_dir)
        mock_get_file_paths.return_value = set()
        mock_can_edit_translation.return_value = True

        response = await async_client.get("/projects/translation-zh-blurb/an-blurbs/")

        assert response.status_code == 200
        assert response.json()["can_edit"] is True
        assert response.json()["data"] == {"an1:0.1": "Test"}
        mock_add_to_index.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "can_edit, data",
        [
            (True, {"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}),
            (False, {"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}),
        ],
    )
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    @patch("app.api.api_v1.endpoints.projects.get_json_data")
    async def test_get_json_data_for_prefix_in_project(
        self,
        mock_get_json_data,
        mock_can_edit_translation,
        mock_get_file_paths,
        async_client,
        mock_get_current_user,
        can_edit,
        data,
        tmp_path,
        monkeypatch,
    ) -> None:
        work_dir = tmp_path / 'unpublished'
        root = work_dir / 'root/pli/ms/an1.1-10_root-pli-ms.json'
        root.parent.mkdir(parents=True)
        root.write_text(json.dumps(data))
        monkeypatch.setattr(settings, 'WORK_DIR', work_dir)
        mock_get_file_paths.return_value = {str(root)}
        mock_can_edit_translation.return_value = can_edit
        mock_get_json_data.return_value = data
        response = await async_client.get("/projects/translation-en-test/an1.1-10/")
        assert response.status_code == 200
        assert "data" in response.json()
        assert "can_edit" in response.json()
        assert response.json() == {
            "can_edit": can_edit,
            "data": data,
            "task_id": None,
            "materialized": True,
            "structure_revision": hashlib.sha256(
                json.dumps([list(data), None], ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest(),
        }

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.get_json_data")
    @patch("app.api.api_v1.endpoints.projects._get_project_file_paths")
    async def test_validate_html_project_uses_the_complete_file_with_draft_overrides(
        self,
        mock_get_project_file_paths,
        mock_get_json_data,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ) -> None:
        mock_get_project_file_paths.return_value = {"html/pli/ms/sutta/mn/mn1_html-pli-ms.json"}
        mock_get_json_data.return_value = {
            "mn1:1.1": "<section><p>{}",
            "mn1:1.2": "</p><span>{}</span></section>",
        }

        response = await async_client.post(
            "/projects/html-pli-ms/mn1/html-validation/",
            json={"overrides": {"mn1:1.2": "</section><p>{}</p>"}},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["checked_segments"] == 2
        assert body["errors"][0]["uid"] == "mn1:1.2"
        assert body["errors"][0]["related_uid"] == "mn1:1.1"

    @pytest.mark.asyncio
    async def test_validate_html_project_rejects_non_html_projects(
        self,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ) -> None:
        response = await async_client.post(
            "/projects/translation-en-test/mn1/html-validation/",
            json={"overrides": {}},
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "HTML validation is only available for html projects"
        }

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.get_json_data")
    @patch("app.api.api_v1.endpoints.projects._get_project_file_paths")
    async def test_validate_html_project_rejects_unknown_draft_uids(
        self,
        mock_get_project_file_paths,
        mock_get_json_data,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ) -> None:
        mock_get_project_file_paths.return_value = {"html/pli/ms/sutta/mn/mn1_html-pli-ms.json"}
        mock_get_json_data.return_value = {"mn1:1.1": "<p>{}</p>"}

        response = await async_client.post(
            "/projects/html-pli-ms/mn1/html-validation/",
            json={"overrides": {"mn1:9.9": "<p>{}</p>"}},
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Unknown HTML segment: mn1:9.9"}

    @pytest.mark.asyncio
    async def test_validate_html_project_requires_admin_or_superuser(
        self,
        async_client,
        mock_get_current_user,
    ) -> None:
        response = await async_client.post(
            "/projects/html-pli-ms/mn1/html-validation/",
            json={"overrides": {}},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_json_data_for_prefix_in_project_unauthenticated(self, async_client) -> None:
        response = await async_client.patch("/projects/translation-en-test/an1.1-10/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    async def test_update_json_data_for_prefix_in_project_cannot_edit_translation(
        self, mock_can_edit_translation, async_client, mock_get_current_user
    ) -> None:
        mock_can_edit_translation.return_value = False
        response = await async_client.patch("/projects/translation-en-test/an1.1-10/", json={"an1.1:0.1": "Test"})
        assert response.status_code == 403
        assert "detail" in response.json()
        assert response.json() == {"detail": "Not allowed to edit this resource"}

    @pytest.mark.asyncio
    async def test_update_json_data_for_prefix_in_project_no_payload(self, async_client, mock_get_current_user) -> None:
        response = await async_client.patch("/projects/translation-en-test/an1.1-10/")
        assert response.status_code == 422
        assert "detail" in response.json()
        detail = response.json()["detail"][0]
        assert detail["type"] == "missing"
        assert detail["loc"] == ["body"]
        assert detail["msg"] == "Field required"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_update_json_data_for_prefix_in_project_invalid_prefix(
        self,
        mock_get_file_paths,
        mock_can_edit_translation,
        async_client,
        mock_get_current_user,
    ) -> None:
        mock_get_file_paths.return_value = set()
        mock_can_edit_translation.return_value = True
        response = await async_client.patch(
            "/projects/translation-en-test/nonexistent_prefix/",
            json={"an1.1:0.1": "Test", "an1.1:0.2": "Test2"},
        )
        assert response.status_code == 404
        assert "detail" in response.json()
        assert response.json() == {
            "detail": "Data for project 'translation-en-test' and prefix 'nonexistent_prefix' not found"
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception, data, code",
        [
            (OSError("Test"), {"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}, 500),
            (TypeError("Test"), {"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}, 500),
            (RequestError, {"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}, 500),
            (KeyError("Test"), {"an1.1:0.1111": "Test", "an1.1:0.2222": "Test2"}, 400),
        ],
    )
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    @patch("app.api.api_v1.endpoints.projects.update_file")
    async def test_update_json_data_for_prefix_in_project_fail(
        self,
        mock_update_file,
        mock_get_file_paths,
        mock_can_edit_translation,
        async_client,
        mock_get_current_user,
        exception,
        data,
        code,
    ) -> None:
        mock_get_file_paths.return_value = set("root/an1.1-10")
        mock_can_edit_translation.return_value = True
        mock_update_file.return_value = False, exception, None
        response = await async_client.patch("/projects/translation-en-test/an1.1-10/", json=data)
        assert response.status_code == code
        assert "detail" in response.json()

    @pytest.mark.asyncio
    @patch("app.tasks.commit.delay")
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    @patch("app.api.api_v1.endpoints.projects.update_file")
    async def test_update_json_data_for_prefix_in_project_success(
        self,
        mock_update_file,
        mock_get_file_paths,
        mock_can_edit_translation,
        mock_commit,
        async_client,
        mock_get_current_user,
    ) -> None:
        data = {"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}
        mock_get_file_paths.return_value = set("root/an1.1-10")
        mock_can_edit_translation.return_value = True
        mock_commit.return_value = "test_task_id"
        mock_update_file.return_value = True, None, "test_task_id"
        response = await async_client.patch("/projects/translation-en-test/an1.1-10/", json=data)
        assert response.status_code == 200
        assert "can_edit" in response.json()
        assert "data" in response.json()
        assert "task_id" in response.json()
        assert response.json() == {
            "can_edit": True,
            "data": data,
            "task_id": "test_task_id",
            "materialized": True,
            "structure_revision": None,
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("can_edit", [True, False])
    @patch("app.api.api_v1.endpoints.projects.can_edit_translation")
    async def test_get_can_edit(self, mock_can_edit_translation, can_edit, async_client, mock_get_current_user) -> None:
        mock_can_edit_translation.return_value = can_edit
        response = await async_client.get("/projects/translation-en-test/can-edit/")
        assert response.status_code == 200
        assert "can_edit" in response.json()
        assert response.json() == {"can_edit": can_edit}

    @pytest.mark.asyncio
    async def test_get_can_edit_unauthenticated(self, async_client) -> None:
        response = await async_client.get("/projects/translation-en-test/can-edit/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    async def test_create_project_unauthenticated(self, async_client) -> None:
        response = await async_client.post("/projects/root/pli/ms/sutta/test/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_create_projects")
    async def test_create_project_invalid_permissions(
        self, mock_can_create_projects, async_client, mock_get_current_user_admin
    ) -> None:
        mock_can_create_projects.return_value = False
        response = await async_client.post("/projects/root/pli/ms/sutta/test/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "detail" in response.json()
        assert response.json() == {"detail": "You are not allowed to create projects"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_create_projects")
    async def test_create_project_data_and_not_json_suffix(
        self, mock_can_create_projects, async_client, mock_get_current_user_admin
    ) -> None:
        mock_can_create_projects.return_value = True
        response = await async_client.post("/projects/root/pli/ms/sutta/test/", json={"test1:0.1": "test"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "detail" in response.json()
        assert response.json() == {"detail": "Path root/pli/ms/sutta/test and related were not created"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_create_projects")
    @patch("app.api.api_v1.endpoints.projects.create_directory")
    @pytest.mark.parametrize(
        "create_dir_result,expected_status,expected_message",
        [
            (True, status.HTTP_201_CREATED, "Directory root/pli/ms/sutta/test and related have been created"),
            (False, status.HTTP_400_BAD_REQUEST, "Directory root/pli/ms/sutta/test and related were not created"),
        ],
    )
    async def test_create_project_directory(
        self,
        mock_create_directory,
        mock_can_create_projects,
        async_client,
        mock_get_current_user_admin,
        create_dir_result,
        expected_status,
        expected_message,
    ) -> None:
        mock_can_create_projects.return_value = True
        mock_create_directory.return_value = create_dir_result
        response = await async_client.post("/projects/root/pli/ms/sutta/test/")
        assert response.status_code == expected_status
        assert "detail" in response.json()
        assert response.json() == {"detail": expected_message}

    @pytest.mark.parametrize("validate_root_data", [(True,), (False,)])
    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_create_projects")
    @patch("app.api.api_v1.endpoints.projects.create_file")
    @patch("app.api.api_v1.endpoints.projects.validate_root_data")
    @pytest.mark.parametrize(
        "create_file_result,expected_status,expected_message",
        [
            (True, status.HTTP_201_CREATED, "File root/pli/ms/sutta/test.json and related have been created"),
            (False, status.HTTP_400_BAD_REQUEST, "File root/pli/ms/sutta/test.json and related were not created"),
        ],
    )
    async def test_create_project_file(
        self,
        mock_validate_root_data,
        mock_create_file,
        mock_can_create_projects,
        async_client,
        mock_get_current_user_admin,
        validate_root_data,
        create_file_result,
        expected_status,
        expected_message,
    ) -> None:
        mock_can_create_projects.return_value = True
        mock_validate_root_data.return_value = validate_root_data
        mock_create_file.return_value = create_file_result
        response = await async_client.post("/projects/root/pli/ms/sutta/test.json/", json={"test1:0.1": "test"})
        assert response.status_code == expected_status
        assert "detail" in response.json()
        assert response.json() == {"detail": expected_message}

    @pytest.mark.asyncio
    async def test_delete_segment_ids_unauthenticated(self, async_client) -> None:
        response = await async_client.patch(
            "/projects/translation/en/test/sutta/test/test1/test1.1-10_translation-en-test.json/",
            params={"dry_run": True, "exact": False},
            json=["an1.1:0.1"],
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_delete_projects")
    async def test_delete_segment_ids_invalid_permissions(
        self, mock_can_delete_projects, async_client, mock_validate_path, mock_get_current_user
    ) -> None:
        mock_can_delete_projects.return_value = False
        response = await async_client.patch(
            "/projects/translation/en/test/sutta/test/test1/test1.1-10_translation-en-test.json/",
            params={"dry_run": True, "exact": False},
            json=["an1.1:0.1"],
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "detail" in response.json()
        assert response.json() == {"detail": "You are not allowed to change projects"}

    @pytest.mark.parametrize("exact", [True, False])
    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_delete_projects")
    @patch("app.api.api_v1.endpoints.projects.UIDReducer")
    @patch("app.api.api_v1.endpoints.projects.get_json_data")
    @patch("app.api.api_v1.endpoints.projects.get_muid")
    async def test_delete_segment_ids_dry_run(
        self,
        mock_get_muid,
        mock_get_json_data,
        mock_uid_reducer,
        mock_can_delete_projects,
        exact,
        async_client,
        mock_validate_path,
        mock_get_current_user_admin,
    ):
        path_str = "translation/en/test/sutta/test/test1/test1.1-10_translation-en-test.json"
        return_value = {"an1.1:0.1": "new_value"} if exact else {}
        muid = "translation-en-test"
        source_muid = "root-pli-test"
        mock_get_muid.side_effect = [muid, source_muid]
        mock_can_delete_projects.return_value = True
        uid_reducer_instance = mock_uid_reducer.return_value
        uid_reducer_instance.decrement_dry.return_value = {settings.WORK_DIR / path_str: return_value}
        current_value = {"an1.1:0.1": "Test"}
        mock_get_json_data.return_value = current_value
        response = await async_client.patch(
            f"/projects/{path_str}/",
            params={"dry_run": True, "exact": exact},
            json=["an1.1:0.1"],
        )
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.json()
        assert "results" in response.json()
        assert "muid" in response.json()["results"][0]
        assert "source_muid" in response.json()["results"][0]
        assert "language" in response.json()["results"][0]
        assert "filename" in response.json()["results"][0]
        assert "prefix" in response.json()["results"][0]
        assert "path" in response.json()["results"][0]
        assert "data_after" in response.json()["results"][0]
        assert "data_before" in response.json()["results"][0]
        assert response.json()["message"] == "Dry run successful"
        assert response.json()["results"][0]["path"] == f"/{path_str}"
        assert response.json()["results"][0]["data_after"] == return_value
        assert response.json()["results"][0]["data_before"] == current_value
        assert response.json()["results"][0]["muid"] == muid
        assert response.json()["results"][0]["source_muid"] == source_muid
        assert response.json()["results"][0]["language"] == "en"
        assert response.json()["results"][0]["filename"] == "test1.1-10_translation-en-test.json"
        assert response.json()["results"][0]["prefix"] == "test1.1-10"

    @pytest.mark.parametrize("exact", [True, False])
    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.projects.can_delete_projects")
    @patch("app.api.api_v1.endpoints.projects.UIDReducer")
    @patch("app.api.api_v1.endpoints.projects.get_json_data")
    async def test_delete_segment_ids(
        self,
        mock_get_json_data,
        mock_uid_reducer,
        mock_can_delete_projects,
        exact,
        async_client,
        mock_validate_path,
        mock_get_current_user_admin,
    ):
        path_str = "translation/en/test/sutta/test/test1/test1.1-10_translation-en-test.json"
        mock_can_delete_projects.return_value = True
        uid_reducer_instance = mock_uid_reducer.return_value
        main_task_id = "main_task_id"
        related_task_id = "related_task_id"
        uid_reducer_instance.decrement.return_value = (main_task_id, related_task_id)
        mock_get_json_data.return_value = {"an1.1:0.1": "Test"}
        response = await async_client.patch(
            f"/projects/{path_str}/",
            params={"dry_run": False, "exact": exact},
            json=["an1.1:0.1"],
        )
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.json()
        assert "main_task_id" in response.json()
        assert "related_task_id" in response.json()
        assert response.json()["message"] == "Segment IDs deleted successfully"
        assert response.json()["main_task_id"] == main_task_id
        assert response.json()["related_task_id"] == related_task_id

    @pytest.mark.asyncio
    async def test_create_new_project_by_admin(
        self,
        mocker,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_create_new_project,
        mock_new_project_create_data,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        current_user = copy(mock_user)
        current_user.role = "administrator"
        current_user.id = 66
        current_user.github_id = 66
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]

        source_user_github_id = 123

        root_path = Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json")
        translation_language = "en"

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )
        assert response.status_code == 202
        assert "task_id" in response.json()
        assert "user" in response.json()
        assert "translation_language" in response.json()
        assert response.json()["task_id"] == "test_task_id"

    @pytest.mark.asyncio
    async def test_create_new_project_unauthorized(
        self,
        mocker,
        mock_create_new_project,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        current_user = copy(mock_user)
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]
        source_user_github_id = 123

        root_path = Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json")
        translation_language = "en"

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_new_project_no_target_user(
        self,
        mocker,
        mock_create_new_project,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        current_user = copy(mock_user)
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, None]
        source_user_github_id = 123456879

        root_path = Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json")
        translation_language = "en"

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_new_project_root_not_existing(
        self,
        mocker,
        mock_create_new_project,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        current_user = copy(mock_user)
        current_user.role = "administrator"
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]
        source_user_github_id = 123

        root_path = Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json")
        translation_language = "en"
        mocker.patch("pathlib.Path.exists", return_value=False)

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )

        assert response.status_code == 404
        assert "Root path" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_new_project_root_not_containing_jsons(
        self,
        mocker,
        mock_create_new_project,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        current_user = copy(mock_user)
        current_user.role = "administrator"
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]
        source_user_github_id = 123

        root_path = Path("root/pli/ms/sutta/an/")
        translation_language = "en"
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.is_dir", return_value=True)
        mocker.patch("pathlib.Path.rglob", return_value=[])

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )

        assert response.status_code == 422
        assert "Root path" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_new_project_root_path_not_starting_in_root_dir(
        self,
        mocker,
        mock_create_new_project,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        current_user = copy(mock_user)
        current_user.role = "administrator"
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]
        source_user_github_id = 123

        root_path = Path("html/root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json")
        translation_language = "en"
        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )

        assert response.status_code == 422
        assert "not starting in 'root/' directory" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_new_project_target_already_exist(
        self,
        mocker,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_create_new_project,
        mock_new_project_create_data,
        mock_user,
        mock_session,
        async_client,
    ) -> None:
        """Endpoint now dispatches a task — it always returns 202 if validation passes.
        The 'already exist' check happens inside the Celery task."""
        current_user = copy(mock_user)
        current_user.role = "administrator"
        current_user.id = 66
        current_user.github_id = 66
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]

        source_user_github_id = 123

        root_path = Path("root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json")
        translation_language = "en"

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": source_user_github_id,
                "root_path": root_path,
                "translation_language": translation_language,
            },
        )

        assert response.status_code == 202
        assert "task_id" in response.json()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_language", ["", "a", "abcd", "abcde"])
    async def test_create_new_project_invalid_language_code(
        self,
        mocker,
        mock_is_admin_or_superuser_is_active,
        mock_get_current_user_admin,
        mock_create_new_project,
        mock_user,
        mock_session,
        async_client,
        invalid_language,
    ) -> None:
        current_user = copy(mock_user)
        current_user.role = "administrator"
        mock_session.query.return_value.filter.return_value.first.side_effect = [current_user, mock_user]

        response = await async_client.post(
            "/projects/create/",
            params={
                "user_github_id": 123,
                "root_path": "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json",
                "translation_language": invalid_language,
            },
        )

        assert response.status_code == 422
        assert "Translation language code must be 2 or 3 characters long" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_source_muid_unauthenticated(self, async_client) -> None:
        response = await async_client.get("/projects/source-muid/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Could not validate credentials"}

    @pytest.mark.asyncio
    async def test_get_source_muid_validate_path_fails(self, async_client, mock_get_current_user, mocker) -> None:
        path = "translation/en/test_user/sutta/an/an1/an1.1-10_translation-en-test_user.json"
        mocker.patch(
            "app.api.api_v1.endpoints.projects.validate_path",
            side_effect=HTTPException(status_code=404, detail="Path not found"),
        )

        response = await async_client.get(f"/projects/{path}/source/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Path not found"}

    @pytest.mark.asyncio
    async def test_get_source_muid(self, async_client, mock_get_current_user, mocker) -> None:
        path = "translation/en/test_user/sutta/an/an1/an1.1-10_translation-en-test_user.json"
        source_muid = "root-pli-ms"
        source_path = "root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"
        mocker.patch("app.api.api_v1.endpoints.projects.validate_path", return_value=settings.WORK_DIR / path)

        response = await async_client.get(f"/projects/{path}/source/")
        assert response.status_code == 200
        assert response.json() == {"muid": source_muid, "path": f"/{source_path}"}
