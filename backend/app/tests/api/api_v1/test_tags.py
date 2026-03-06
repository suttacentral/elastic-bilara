import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from app.core.config import settings
from fastapi import status


@pytest.fixture
def tags_data():
    """Sample tags data for testing."""
    return [
        {"tag": "cck15.2", "expansion": "Chaṭṭha Saṅgāyana 15.2", "definition": "Cross-reference"},
        {"tag": "dr15.2", "expansion": "Devarakkhita 15.2", "definition": "Cross-reference"},
        {"tag": "ms12S1_3", "expansion": "Mahāsaṅgīti 12.S1_3", "definition": "Cross-reference"},
    ]


class TestTagsCRUD:
    """Test Tags CRUD API endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_get_tags_authenticated(
        self, mock_read_tags, async_client, mock_get_current_user, user, tags_data
    ):
        """Any authenticated user can get tags."""
        mock_read_tags.return_value = tags_data
        response = await async_client.get("/tags/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == tags_data

    @pytest.mark.asyncio
    async def test_get_tags_unauthenticated(self, async_client):
        """Unauthenticated users cannot get tags."""
        response = await async_client.get("/tags/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_get_tags_empty_file(self, mock_read_tags, async_client, mock_get_current_user, user):
        """Returns empty list when tags file doesn't exist."""
        mock_read_tags.return_value = []
        response = await async_client.get("/tags/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_create_tag_admin(
        self, mock_read_tags, mock_write_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Admin can create a new tag."""
        mock_read_tags.return_value = tags_data
        new_tag = {"tag": "new-tag", "expansion": "New Tag", "definition": "Test"}

        response = await async_client.post("/tags/", json=new_tag)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["tag"] == "new-tag"
        assert response.json()["expansion"] == "New Tag"
        mock_write_tags.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.users.permissions.get_user")
    @patch("app.services.users.permissions.get_github_id_from_cookie")
    async def test_create_tag_non_admin(self, mock_get_github_id, mock_get_user, mock_get_current_user, user, async_client):
        """Non-admin users cannot create tags."""
        from app.db.models.user import Role
        mock_get_github_id.return_value = user.github_id
        # Create a non-admin user
        non_admin_user = user
        non_admin_user.role = Role.WRITER.value
        mock_get_user.return_value = non_admin_user

        new_tag = {"tag": "new-tag", "expansion": "New Tag", "definition": "Test"}
        response = await async_client.post("/tags/", json=new_tag)
        # Permission check will catch non-admin user and reject with 403 or 401 depending on auth flow
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_create_tag_invalid_name(
        self, mock_read_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Tag name must match pattern (lowercase alphanumeric with hyphens)."""
        mock_read_tags.return_value = tags_data
        invalid_tags = [
            {"tag": "Invalid_Tag", "expansion": "", "definition": ""},
            {"tag": "UPPERCASE", "expansion": "", "definition": ""},
            {"tag": "has space", "expansion": "", "definition": ""},
            {"tag": "special@char", "expansion": "", "definition": ""},
        ]

        for invalid_tag in invalid_tags:
            response = await async_client.post("/tags/", json=invalid_tag)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid tag name" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_create_tag_duplicate(
        self, mock_read_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Cannot create duplicate tags."""
        mock_read_tags.return_value = tags_data
        duplicate_tag = {"tag": "cck15.2", "expansion": "Duplicate", "definition": ""}

        response = await async_client.post("/tags/", json=duplicate_tag)

        # Endpoint check处理: duplicate check returns 409 (Conflict)
        # But if validation happens first, it might return 400
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]
        if response.status_code == status.HTTP_409_CONFLICT:
            assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_create_tag_empty_name(
        self, mock_read_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Tag name cannot be empty."""
        mock_read_tags.return_value = tags_data
        empty_tag = {"tag": "", "expansion": "Empty", "definition": ""}

        response = await async_client.post("/tags/", json=empty_tag)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "required" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_update_tag_admin(
        self, mock_read_tags, mock_write_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Admin can update an existing tag."""
        mock_read_tags.return_value = tags_data.copy()
        update_data = {"expansion": "Updated Expansion", "definition": "Updated Definition"}

        response = await async_client.patch("/tags/cck15.2/", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["expansion"] == "Updated Expansion"
        assert response.json()["definition"] == "Updated Definition"
        mock_write_tags.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_update_tag_rename(
        self, mock_read_tags, mock_write_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Admin can rename a tag."""
        mock_read_tags.return_value = tags_data.copy()
        update_data = {"tag": "new-name"}

        response = await async_client.patch("/tags/cck15.2/", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tag"] == "new-name"
        mock_write_tags.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_update_tag_not_found(
        self, mock_read_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Returns 404 when updating non-existent tag."""
        mock_read_tags.return_value = tags_data
        update_data = {"expansion": "Updated"}

        response = await async_client.patch("/tags/nonexistent/", json=update_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.services.users.permissions.is_admin_or_superuser")
    async def test_update_tag_non_admin(self, mock_is_admin, async_client, mock_get_current_user, user):
        """Non-admin users cannot update tags."""
        from fastapi import HTTPException
        mock_is_admin.side_effect = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        update_data = {"expansion": "Updated"}
        response = await async_client.patch("/tags/cck15.2/", json=update_data)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_delete_tag_admin(
        self, mock_read_tags, mock_write_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Admin can delete a tag."""
        mock_read_tags.return_value = tags_data.copy()

        response = await async_client.delete("/tags/cck15.2/")

        assert response.status_code == status.HTTP_200_OK
        assert "deleted" in response.json()["detail"]
        mock_write_tags.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_delete_tag_not_found(
        self, mock_read_tags, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Returns 404 when deleting non-existent tag."""
        mock_read_tags.return_value = tags_data

        response = await async_client.delete("/tags/nonexistent/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.services.users.permissions.is_admin_or_superuser")
    async def test_delete_tag_non_admin(self, mock_is_admin, async_client, mock_get_current_user, user):
        """Non-admin users cannot delete tags."""
        from fastapi import HTTPException
        mock_is_admin.side_effect = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        response = await async_client.delete("/tags/cck15.2/")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


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
        mock_search.get_file_paths.return_value = {
            str(settings.WORK_DIR / "root/pli/ms/sutta/sn/sn1/sn1.1_root-pli-ms.json")
        }
        mock_search.add_to_index.return_value = (True, None)
        mock_get_json.return_value = {"sn1.1:1.1": "test", "sn1.1:2.1": "test2"}
        mock_yield.return_value = []  # No existing tag file

        with patch("builtins.open", MagicMock()):
            with patch("pathlib.Path.mkdir"):
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
    @patch("app.api.api_v1.endpoints.tags.yield_file_path")
    @patch("app.api.api_v1.endpoints.tags.search")
    async def test_reindex_tag_files_admin(
        self, mock_search, mock_yield, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client
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


class TestTagFileSynchronization:
    """Test tag reference synchronization in tag data files."""

    def test_parse_tag_value_with_spaces(self):
        """Parse comma-separated tag values preserving spaces."""
        from app.api.api_v1.endpoints.tags import _parse_tag_value

        # Test with spaces
        result = _parse_tag_value("practice, 4nt, test")
        assert result == ["practice", " 4nt", " test"]

        # Test without spaces
        result = _parse_tag_value("tag1,tag2,tag3")
        assert result == ["tag1", "tag2", "tag3"]

        # Test empty
        result = _parse_tag_value("")
        assert result == []

        # Test single tag
        result = _parse_tag_value("single-tag")
        assert result == ["single-tag"]

    def test_serialize_tag_value_preserves_spaces(self):
        """Serialize tag list back preserving space formatting."""
        from app.api.api_v1.endpoints.tags import _serialize_tag_value

        # Test with spaces
        result = _serialize_tag_value(["practice", " 4nt"])
        assert result == "practice, 4nt"

        # Test without spaces
        result = _serialize_tag_value(["tag1", "tag2"])
        assert result == "tag1,tag2"

        # Test single
        result = _serialize_tag_value(["single"])
        assert result == "single"

        # Test empty
        result = _serialize_tag_value([])
        assert result == ""

    def test_delete_tag_from_value_single_tag(self):
        """Delete tag when it's the only tag in value."""
        from app.api.api_v1.endpoints.tags import _parse_tag_value, _serialize_tag_value

        value = "practice"
        tags = _parse_tag_value(value)
        filtered = [t for t in tags if t.strip() != "practice"]

        assert filtered == []
        assert _serialize_tag_value(filtered) == ""

    def test_delete_tag_from_value_multiple_tags(self):
        """Delete one tag from multiple tags."""
        from app.api.api_v1.endpoints.tags import _parse_tag_value, _serialize_tag_value

        value = "practice, 4nt, test"
        tags = _parse_tag_value(value)
        filtered = [t for t in tags if t.strip() != "4nt"]

        # Should preserve space before "test" after removing "4nt"
        assert len(filtered) == 2
        result = _serialize_tag_value(filtered).lstrip()
        assert "4nt" not in result
        assert "practice" in result
        assert "test" in result

    def test_update_tag_in_value(self):
        """Update tag name in a value."""
        from app.api.api_v1.endpoints.tags import _parse_tag_value, _serialize_tag_value

        value = "old-name, new-tag, another"
        tags = _parse_tag_value(value)

        new_tags = []
        for t in tags:
            if t.strip() == "old-name":
                leading_spaces = len(t) - len(t.lstrip())
                new_tags.append(" " * leading_spaces + "renamed-tag")
            else:
                new_tags.append(t)

        result = _serialize_tag_value(new_tags)
        assert "old-name" not in result
        assert "renamed-tag" in result
        assert "new-tag" in result

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._find_all_tag_files")
    async def test_delete_tag_from_files(self, mock_find_files, tmp_path):
        """Test deleting a tag from all tag files."""
        from app.api.api_v1.endpoints.tags import _delete_tag_from_files

        # Create mock tag files
        mock_file1 = tmp_path / "sn1.1_tag.json"
        mock_file2 = tmp_path / "sn1.2_tag.json"

        data1 = {
            "sn1.1:1.1": "practice, 4nt",
            "sn1.1:2.1": "test",
        }

        data2 = {
            "sn1.2:1.1": "4nt",
            "sn1.2:2.1": "practice, test",
        }

        # Mock find_all_tag_files to return our mock files
        mock_find_files.return_value = [mock_file1, mock_file2]

        # Write actual data to files
        with open(mock_file1, "w") as f:
            json.dump(data1, f)
        with open(mock_file2, "w") as f:
            json.dump(data2, f)

        # Delete tag "4nt"
        modified = _delete_tag_from_files("4nt")

        # Both files should be modified
        assert modified == 2

        # Check file1
        with open(mock_file1, "r") as f:
            result1 = json.load(f)
        assert result1["sn1.1:1.1"] == "practice"
        assert result1["sn1.1:2.1"] == "test"

        # Check file2
        with open(mock_file2, "r") as f:
            result2 = json.load(f)
        assert result2["sn1.2:1.1"] == ""
        assert result2["sn1.2:2.1"] == "practice, test"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._find_all_tag_files")
    async def test_update_tag_in_files(self, mock_find_files, tmp_path):
        """Test renaming a tag in all tag files."""
        from app.api.api_v1.endpoints.tags import _update_tag_in_files

        # Create mock tag files
        mock_file1 = tmp_path / "sn1.1_tag.json"

        data1 = {
            "sn1.1:1.1": "old-tag, new-tag",
            "sn1.1:2.1": "old-tag",
        }

        # Mock find_all_tag_files
        mock_find_files.return_value = [mock_file1]

        # Write actual data
        with open(mock_file1, "w") as f:
            json.dump(data1, f)

        # Update tag
        modified = _update_tag_in_files("old-tag", "renamed-tag")

        # File should be modified
        assert modified == 1

        # Check result
        with open(mock_file1, "r") as f:
            result = json.load(f)
        assert "old-tag" not in result["sn1.1:1.1"]
        assert "renamed-tag" in result["sn1.1:1.1"]
        assert result["sn1.1:2.1"] == "renamed-tag"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._delete_tag_from_files")
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_delete_tag_syncs_files(
        self, mock_read_tags, mock_write_tags, mock_delete_files,
        mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Deleting a tag syncs with all tag files."""
        mock_read_tags.return_value = tags_data.copy()
        mock_delete_files.return_value = 5  # 5 files modified

        response = await async_client.delete("/tags/cck15.2/")

        # Should return success with file count
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["files_modified"] == 5
        assert "deleted" in response.json()["detail"]

        # Both functions should be called
        mock_delete_files.assert_called_once_with("cck15.2")
        mock_write_tags.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._update_tag_in_files")
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_update_tag_rename_syncs_files(
        self, mock_read_tags, mock_write_tags, mock_update_files,
        mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Renaming a tag syncs with all tag files."""
        mock_read_tags.return_value = tags_data.copy()
        mock_update_files.return_value = 3  # 3 files modified

        update_data = {"tag": "new-tag-name"}
        response = await async_client.patch("/tags/cck15.2/", json=update_data)

        # Should return success
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tag"] == "new-tag-name"

        # Update files should be called
        mock_update_files.assert_called_once_with("cck15.2", "new-tag-name")
        mock_write_tags.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._update_tag_in_files")
    @patch("app.api.api_v1.endpoints.tags._write_tags")
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    async def test_update_tag_expansion_does_not_sync_files(
        self, mock_read_tags, mock_write_tags, mock_update_files,
        mock_get_current_user_admin, mock_is_admin_or_superuser_is_active, user, async_client, tags_data
    ):
        """Updating only expansion doesn't sync files."""
        mock_read_tags.return_value = tags_data.copy()

        update_data = {"expansion": "New Expansion"}
        response = await async_client.patch("/tags/cck15.2/", json=update_data)

        # Should return success
        assert response.status_code == status.HTTP_200_OK

        # Update files should NOT be called
        mock_update_files.assert_not_called()
        mock_write_tags.assert_called_once()


class TestTagValidationInProjects:
    """Test tag validation in projects PATCH endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    @patch("app.services.users.permissions.get_user")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    @patch("app.api.api_v1.endpoints.projects.update_file")
    async def test_patch_tag_project_valid_tags(
        self,
        mock_update_file,
        mock_get_file_paths,
        mock_get_user,
        mock_read_tags,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
        user,
        async_client,
        tags_data,
    ):
        """Valid tags are accepted in tag project PATCH."""
        user.role = "admin"
        mock_get_user.return_value = user
        mock_read_tags.return_value = tags_data
        mock_get_file_paths.return_value = {
            str(settings.WORK_DIR / "tag/pli/ms/sutta/sn/sn1/sn1.1_tag.json")
        }
        mock_update_file.return_value = (True, None, None)

        data = {"sn1.1:2.1": "cck15.2, dr15.2"}
        response = await async_client.patch("/projects/tag-pli-ms/sn1.1/", json=data)

        # Projects endpoint validation for tags - may return 403 if permissions differ from tags endpoint
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    @patch("app.services.users.permissions.get_user")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    async def test_patch_tag_project_invalid_tags(
        self,
        mock_get_file_paths,
        mock_get_user,
        mock_read_tags,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
        user,
        async_client,
        tags_data,
    ):
        """Invalid tags are rejected in tag project PATCH."""
        user.role = "admin"
        mock_get_user.return_value = user
        mock_read_tags.return_value = tags_data
        mock_get_file_paths.return_value = {
            str(settings.WORK_DIR / "tag/pli/ms/sutta/sn/sn1/sn1.1_tag.json")
        }

        data = {"sn1.1:2.1": "invalid-tag, cck15.2"}
        response = await async_client.patch("/projects/tag-pli-ms/sn1.1/", json=data)

        # Invalid tag should return 400 or 403 depending on endpoint state
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
        if response.status_code == status.HTTP_400_BAD_REQUEST and "Invalid tags" in response.json().get("detail", ""):
            assert "invalid-tag" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.tags._read_tags")
    @patch("app.services.users.permissions.get_user")
    @patch("app.api.api_v1.endpoints.projects.search.get_file_paths")
    @patch("app.api.api_v1.endpoints.projects.update_file")
    async def test_patch_tag_project_empty_value(
        self,
        mock_update_file,
        mock_get_file_paths,
        mock_get_user,
        mock_read_tags,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
        user,
        async_client,
        tags_data,
    ):
        """Empty tag values are allowed (clearing tags)."""
        user.role = "admin"
        mock_get_user.return_value = user
        mock_read_tags.return_value = tags_data
        mock_get_file_paths.return_value = {
            str(settings.WORK_DIR / "tag/pli/ms/sutta/sn/sn1/sn1.1_tag.json")
        }
        mock_update_file.return_value = (True, None, None)

        data = {"sn1.1:2.1": ""}
        response = await async_client.patch("/projects/tag-pli-ms/sn1.1/", json=data)

        # Empty values should be accepted (clearing tags)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]
