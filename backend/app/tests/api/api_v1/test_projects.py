from unittest.mock import patch

import pytest
from elasticsearch import RequestError


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
        assert "root_paths" in response.json()
        assert len(response.json()["root_paths"]) == 2
        assert response.json() == {"root_paths": ["root/path1", "root/path2"]}
        print(mock_get_file_paths.call_args_list)
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
        assert response.json() == {"detail": "Not authenticated"}

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
    ) -> None:
        mock_get_file_paths.return_value = set("root/an1.1-10")
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
        }

    @pytest.mark.asyncio
    async def test_update_json_data_for_prefix_in_project_unauthenticated(self, async_client) -> None:
        response = await async_client.patch("/projects/translation-en-test/an1.1-10/")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert response.json() == {"detail": "Not authenticated"}

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
        assert response.json() == {
            "detail": [
                {
                    "type": "missing",
                    "loc": ["body"],
                    "msg": "Field required",
                    "input": None,
                    "url": "https://errors.pydantic.dev/2.3/v/missing",
                }
            ]
        }

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
        assert response.json() == {"can_edit": True, "data": data, "task_id": "test_task_id"}
