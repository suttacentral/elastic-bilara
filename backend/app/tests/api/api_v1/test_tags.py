import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from app.core.config import settings
from app.services.projects.structure_store import StructureConflict, StructureStore
from app.services.tags import sync
from app.services.tags.store import TagStore
from fastapi import status


@pytest.fixture(autouse=True)
def tag_work(tmp_path, monkeypatch):
    work = tmp_path / "tag-checkout"
    work.mkdir()
    monkeypatch.setattr(settings, "WORK_DIR", work)
    monkeypatch.setattr(sync, "dispatch_safely", Mock())
    (work / "_tags.json").write_text(json.dumps([
        {"tag": "old", "expansion": "Old", "definition": ""},
        {"tag": "keep", "expansion": "Keep", "definition": ""},
    ]))
    passage = work / "tag/pli/ms/sn1_tag.json"
    passage.parent.mkdir(parents=True)
    passage.write_text(json.dumps({"sn1:1": "old, keep", "sn1:2": "old"}))
    return work


@pytest.mark.asyncio
async def test_read_tags_authenticated(async_client, mock_get_current_user, tag_work):
    response = await async_client.get("/tags/")
    assert response.status_code == 200
    assert response.json() == json.loads((tag_work / "_tags.json").read_text())


@pytest.mark.asyncio
async def test_tag_crud_persists_complete_batches_and_dispatches(
    async_client, mock_is_admin_or_superuser_is_active, tag_work
):
    response = await async_client.post("/tags/", json={"tag": "fresh", "definition": "New"})
    assert response.status_code == 201
    assert response.json()["tag"] == "fresh"
    assert response.json()["_sync"]["status"] == "pending"
    assert TagStore(tag_work).read_sync()["paths"] == ["_tags.json"]
    response = await async_client.patch("/tags/fresh/", json={"definition": "Edited"})
    assert response.status_code == 200
    assert response.json()["definition"] == "Edited"
    response = await async_client.patch("/tags/old/", json={"tag": "renamed"})
    assert response.status_code == 200
    assert response.json()["tag"] == "renamed"
    store = TagStore(tag_work)
    assert store.read_sync()["paths"] == ["_tags.json", "tag/pli/ms/sn1_tag.json"]
    assert json.loads((tag_work / "tag/pli/ms/sn1_tag.json").read_text())["sn1:2"] == "renamed"
    response = await async_client.delete("/tags/renamed/")
    assert response.status_code == 200
    assert response.json()["files_modified"] == 1
    assert json.loads((tag_work / "tag/pli/ms/sn1_tag.json").read_text())["sn1:2"] == ""
    assert sync.dispatch_safely.call_count == 4
    definitions = json.loads((tag_work / "_tags.json").read_text())
    assert all("_sync" not in entry for entry in definitions)
    assert store.read_sync()["user"]["role"] == "administrator"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url,payload,expected", [
    ("post", "/tags/", {"tag": ""}, 400),
    ("post", "/tags/", {"tag": "Bad_Name"}, 400),
    ("post", "/tags/", {"tag": "old"}, 409),
    ("post", "/tags/", {"tag": "fresh", "definition": None}, 422),
    ("patch", "/tags/old/", {"tag": "keep"}, 409),
    ("patch", "/tags/old/", {"tag": "invalid name"}, 400),
    ("patch", "/tags/missing/", {"definition": "Edited"}, 404),
    ("delete", "/tags/missing/", None, 404),
])
async def test_invalid_mutation_does_not_write_or_dispatch(
    async_client, mock_is_admin_or_superuser_is_active, tag_work, method, url, payload, expected
):
    before = (tag_work / "_tags.json").read_bytes()
    response = await async_client.request(method.upper(), url, **({"json": payload} if payload is not None else {}))
    assert response.status_code == expected
    assert (tag_work / "_tags.json").read_bytes() == before
    assert TagStore(tag_work).read_sync() is None
    sync.dispatch_safely.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('error,expected', [
    (StructureConflict('Invalid JSON in structure operation journal.'), 409),
    (OSError('structure journal unavailable'), 503),
])
async def test_structure_query_failure_does_not_write_or_dispatch(
    async_client, mock_is_admin_or_superuser_is_active, tag_work, error, expected
):
    before = {path: path.read_bytes() for path in tag_work.rglob('*.json')}
    with patch.object(StructureStore, 'pending_paths', side_effect=error):
        response = await async_client.patch('/tags/old/', json={'tag': 'renamed'})
    assert response.status_code == expected
    assert all(path.read_bytes() == data for path, data in before.items())
    assert TagStore(tag_work).read_sync() is None
    sync.dispatch_safely.assert_not_called()


@pytest.mark.asyncio
async def test_sync_status_and_retry_survive_reload(async_client, mock_is_admin_or_superuser_is_active, tag_work):
    response = await async_client.get("/tags/sync/")
    assert response.json() == {"status": "idle", "can_retry": False}
    await async_client.post("/tags/", json={"tag": "fresh"})
    store = TagStore(tag_work)
    with store.locked():
        state = store.read_sync()
        state.update(status="failed", error="offline")
        store.write_sync(state)
    response = await async_client.get("/tags/sync/")
    assert response.json()["status"] == "failed"
    assert response.json()["can_retry"]
    response = await async_client.post("/tags/sync/retry/")
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert response.json()["generation"] != state["generation"]
    assert sync.dispatch_safely.call_count == 2
    response = await async_client.post("/tags/sync/retry/")
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url,payload", [
    ("GET", "/tags/", None), ("POST", "/tags/", {"tag": "new"}),
    ("PATCH", "/tags/old/", {"definition": "Edited"}), ("DELETE", "/tags/old/", None),
    ("GET", "/tags/sync/", None), ("POST", "/tags/sync/retry/", None),
])
async def test_unauthenticated_requests_are_rejected(async_client, method, url, payload):
    response = await async_client.request(method, url, **({"json": payload} if payload is not None else {}))
    assert response.status_code == 401
    sync.dispatch_safely.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("role,active", [("writer", True), ("reviewer", True), ("administrator", False)])
async def test_non_admin_or_inactive_cannot_write_or_retry(async_client, user, role, active):
    user = user.model_copy(update={"role": role, "is_active": active})
    with patch("app.services.users.permissions.get_github_id_from_cookie", return_value=user.github_id), patch(
        "app.services.users.permissions.get_user", return_value=user
    ):
        for method, url, payload in [("POST", "/tags/", {"tag": "new"}),
                                     ("PATCH", "/tags/old/", {"definition": "Edited"}),
                                     ("DELETE", "/tags/old/", None),
                                     ("POST", "/tags/sync/retry/", None)]:
            response = await async_client.request(method, url, **({"json": payload} if payload else {}))
            assert response.status_code in (401, 403)
    sync.dispatch_safely.assert_not_called()


class TestTagDataFile:
    """Test tag data file creation and reindexing."""

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags.yield_file_path")
    @patch("app.api.api_v1.endpoints.tags.get_json_data")
    @patch("app.api.api_v1.endpoints.tags.search")
    async def test_create_tag_data_file_admin(
        self, mock_search, mock_get_json, mock_yield, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client
    ):
        """Admin can create tag data file for a prefix."""
        root = settings.WORK_DIR / "root/pli/ms/sutta/sn/sn1/sn1.1_root-pli-ms.json"
        root.parent.mkdir(parents=True)
        root.write_text('{}')
        mock_search.get_file_paths.return_value = {str(root)}
        mock_search.add_to_index.return_value = (True, None)
        mock_get_json.return_value = {"sn1.1:1.1": "test", "sn1.1:2.1": "test2"}
        mock_yield.return_value = []  # No existing tag file

        response = await async_client.post("/tags/data/sn1.1/")

        assert response.status_code == status.HTTP_201_CREATED
        assert "created" in response.json()["detail"]
        assert "path" in response.json()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags.search")
    async def test_create_tag_data_file_no_root(
        self, mock_search, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client
    ):
        """Returns 404 when root file not found."""
        mock_search.get_file_paths.return_value = set()

        response = await async_client.post("/tags/data/nonexistent/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.services.users.permissions.is_admin_or_superuser")
    async def test_create_tag_data_file_non_admin(self, mock_is_admin, async_client, mock_get_current_user, user):
        """Non-admin users cannot create tag data files."""
        from fastapi import HTTPException
        mock_is_admin.side_effect = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        response = await async_client.post("/tags/data/sn1.1/")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags.Path.exists", return_value=True)
    @patch("app.api.api_v1.endpoints.tags.yield_file_path")
    @patch("app.api.api_v1.endpoints.tags.search")
    async def test_reindex_tag_files_admin(
        self, mock_search, mock_yield, mock_exists, mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active, user, async_client
    ):
        """Admin can reindex all tag files."""
        mock_file1 = Path("/app/checkouts/unpublished/tag/pli/ms/sutta/sn/sn1/sn1.1_tag.json")
        mock_file2 = Path("/app/checkouts/unpublished/tag/pli/ms/sutta/sn/sn1/sn1.2_tag.json")
        mock_yield.return_value = [mock_file1, mock_file2]
        mock_search.add_to_index.return_value = (True, None)

        response = await async_client.post("/tags/reindex/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["indexed"] == 2

    @pytest.mark.asyncio
    @patch("app.services.users.permissions.is_admin_or_superuser")
    async def test_reindex_tag_files_non_admin(self, mock_is_admin, async_client, mock_get_current_user, user):
        """Non-admin users cannot reindex tag files."""
        from fastapi import HTTPException
        mock_is_admin.side_effect = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        response = await async_client.post("/tags/reindex/")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
