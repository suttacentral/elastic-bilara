import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest
from app.core.config import settings
from pygit2 import (
    GitError,
    GIT_STATUS_INDEX_NEW,
    GIT_STATUS_INDEX_MODIFIED,
    GIT_STATUS_INDEX_DELETED,
    GIT_STATUS_WT_MODIFIED,
    GIT_STATUS_WT_NEW,
    GIT_STATUS_WT_DELETED,
)


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(async_client):
    response = await async_client.post(
        "/git/sync",
        headers={"x-hub-signature-256": "sha256=1234", "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid signature"}


@pytest.mark.asyncio
async def test_github_webhook_invalid_branch(async_client):
    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    payload = {"pull_request": {"base": {"ref": "refs/heads/invalid"}}}
    payload_bytes = json.dumps(payload).encode("utf-8")
    with patch("app.api.api_v1.endpoints.git_ops.parse_payload", return_value=payload):
        signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
        response = await async_client.post(
            "/git/sync",
            headers={"x-hub-signature-256": f"sha256={signature}", "Content-Type": "application/x-www-form-urlencoded"},
            json={"pull_request": {"base": {"ref": "refs/heads/invalid"}}},
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid branch name. Use 'published' or 'unpublished'"}


@pytest.mark.asyncio
async def test_github_webhook_valid_branch(async_client, mock_users):
    with patch("app.api.api_v1.endpoints.git_ops.hmac.compare_digest", return_value=True):
        with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_users[0]):
            with patch("app.api.api_v1.endpoints.git_ops.pull.delay", return_value=MagicMock(id="123456")):
                with patch("app.api.api_v1.endpoints.git_ops.push.delay", return_value=MagicMock(id="654321")):
                    payload = {"pull_request": {"base": {"ref": "refs/heads/published"}}, "sender": {"id": 123456}}
                    with patch("app.api.api_v1.endpoints.git_ops.parse_payload", return_value=payload):
                        response = await async_client.post(
                            "/git/sync",
                            headers={
                                "x-hub-signature-256": f"sha256={settings.GITHUB_WEBHOOK_SECRET.encode()}}}",
                                "Content-Type": "application/x-www-form-urlencoded",
                            },
                            json=payload,
                        )
                        assert response.status_code == 201
                        assert response.json() == {
                            "detail": "Sync action has been triggered",
                            "task_id": ["123456", "654321"],
                        }


@pytest.mark.asyncio
async def test_sync_repository_data_unauthorized(async_client):
    response = await async_client.get("/git/sync/published")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_repository_data_invalid_branch(
    async_client, mock_get_current_user, mock_is_admin_or_superuser_is_active, mock_users
):
    mock_users[0].role = "administrator"
    with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_users[0]):
        response = await async_client.get("/git/sync/invalid")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid branch name. Use 'published' or 'unpublished'"}


@pytest.mark.asyncio
async def test_sync_repository_data_valid_branch(
    async_client, mock_get_current_user, mock_is_admin_or_superuser_is_active, mock_users
):
    mock_users[0].role = "administrator"
    with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_users[0]):
        with patch("app.api.api_v1.endpoints.git_ops.pull.delay", return_value=MagicMock(id="123456")):
            with patch("app.api.api_v1.endpoints.git_ops.push.delay", return_value=MagicMock(id="654321")):
                response = await async_client.get("/git/sync/published")

                assert response.status_code == 201
                assert response.json() == {"detail": "Sync action has been triggered", "task_id": ["123456", "654321"]}


# Tests for get_git_status endpoint
class TestGetGitStatus:
    """Tests for GET /git/status endpoint"""

    @pytest.mark.asyncio
    async def test_get_git_status_unauthorized(self, async_client):
        """Test that unauthorized users cannot access git status"""
        response = await async_client.get("/git/status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_empty_repository(
        self, mock_ensure_safe, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test git status with no modified files"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.return_value = {}

        response = await async_client.get("/git/status")

        assert response.status_code == 200
        assert response.json() == {"files": [], "total": 0}
        mock_ensure_safe.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_with_modified_files(
        self, mock_ensure_safe, mock_repository_class, mock_get_status_name, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test git status with multiple modified files"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.return_value = {
            "translation/en/test.json": GIT_STATUS_WT_MODIFIED,
            "comment/en/test.json": GIT_STATUS_WT_NEW,
            "root/en/test.json": GIT_STATUS_WT_DELETED,
        }
        mock_get_status_name.side_effect = lambda x: {
            GIT_STATUS_WT_MODIFIED: "modified",
            GIT_STATUS_WT_NEW: "new",
            GIT_STATUS_WT_DELETED: "deleted",
        }[x]

        response = await async_client.get("/git/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["files"]) == 3
        # Verify files are sorted by path
        paths = [f["path"] for f in data["files"]]
        assert paths == sorted(paths)

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_filters_hidden_files(
        self, mock_ensure_safe, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test that hidden files and directories (starting with . or _) are filtered out"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.return_value = {
            "translation/en/test.json": GIT_STATUS_WT_MODIFIED,
            ".hidden/file.json": GIT_STATUS_WT_MODIFIED,
            "_internal/file.json": GIT_STATUS_WT_MODIFIED,
            "path/.hidden.json": GIT_STATUS_WT_NEW,
            "path/_internal.json": GIT_STATUS_WT_NEW,
        }

        with patch("app.api.api_v1.endpoints.git_ops.get_status_name", return_value="modified"):
            response = await async_client.get("/git/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["files"]) == 1
        assert data["files"][0]["path"] == "translation/en/test.json"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_git_error(
        self, mock_ensure_safe, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test git status handling of GitError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.side_effect = GitError("Git repository error")

        response = await async_client.get("/git/status")

        assert response.status_code == 500
        assert "Git error" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_permission_error(
        self, mock_ensure_safe, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test git status handling of PermissionError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.side_effect = PermissionError("Permission denied")

        response = await async_client.get("/git/status")

        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_os_error(
        self, mock_ensure_safe, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test git status handling of OSError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.side_effect = OSError("OS error")

        response = await async_client.get("/git/status")

        assert response.status_code == 500
        assert "OS error" in response.json()["detail"]


# Tests for get_file_diff endpoint
class TestGetFileDiff:
    """Tests for GET /git/diff/{file_path} endpoint"""

    @pytest.mark.asyncio
    async def test_get_file_diff_unauthorized(self, async_client):
        """Test that unauthorized users cannot access file diff"""
        response = await async_client.get("/git/diff/test.json")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_new_file(
        self, mock_repository_class, mock_get_status_name, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a new file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW
        mock_get_status_name.return_value = "new"

        file_content = "line1\nline2\nline3"
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = file_content

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.json"
        assert data["status"] == "new"
        assert "+++ test.json" in data["diff"]
        assert "+line1" in data["diff"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_new_file_not_exists(
        self, mock_repository_class, mock_get_status_name, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a new file that doesn't exist"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW
        mock_get_status_name.return_value = "new"

        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["diff"] == "New file: test.json"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_deleted_file(
        self, mock_repository_class, mock_get_status_name, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a deleted file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_DELETED
        mock_get_status_name.return_value = "deleted"

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.json"
        assert data["status"] == "deleted"
        assert data["diff"] == "--- test.json\nFile deleted"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_modified_file_with_diff(
        self, mock_repository_class, mock_get_status_name, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a modified file with diff content"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_MODIFIED
        mock_get_status_name.return_value = "modified"

        # Mock diff
        mock_patch = MagicMock()
        mock_patch.delta.new_file.path = "test.json"
        mock_patch.delta.old_file.path = "test.json"
        mock_patch.text = "diff --git a/test.json b/test.json\n-old line\n+new line"

        mock_diff = MagicMock()
        mock_diff.__iter__.return_value = [mock_patch]
        mock_repo.diff.return_value = mock_diff

        mock_head = MagicMock()
        mock_tree = MagicMock()
        mock_head.peel.return_value.tree = mock_tree
        mock_repo.head = mock_head

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.json"
        assert data["status"] == "modified"
        assert "diff --git" in data["diff"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_modified_file_no_diff(
        self, mock_repository_class, mock_get_status_name, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a modified file when diff is empty"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_MODIFIED
        mock_get_status_name.return_value = "modified"

        # Mock empty diff
        mock_diff = MagicMock()
        mock_diff.__iter__.return_value = []
        mock_repo.diff.return_value = mock_diff

        mock_head = MagicMock()
        mock_tree = MagicMock()
        mock_head.peel.return_value.tree = mock_tree
        mock_repo.head = mock_head

        file_content = "modified content"
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = file_content

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert "Modified file content:" in data["diff"]
        assert file_content in data["diff"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_file_not_found(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a file that doesn't exist in repository"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.side_effect = KeyError("File not found")

        response = await async_client.get("/git/diff/nonexistent.json")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_no_changes(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff for a file with no changes"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = 0  # No changes

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 400
        assert "File has no changes" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_get_file_diff_git_error(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test diff handling of GitError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.side_effect = GitError("Git error")

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 500
        assert "Git error" in response.json()["detail"]


# Tests for discard_file_changes endpoint
class TestDiscardFileChanges:
    """Tests for POST /git/discard endpoint"""

    @pytest.mark.asyncio
    async def test_discard_file_changes_unauthorized(self, async_client):
        """Test that unauthorized users cannot discard changes"""
        response = await async_client.post("/git/discard", json={"file_path": "test.json"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_new_file(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a new untracked file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink.return_value = None
        mock_path.parent.exists.return_value = False

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Deleted untracked file" in data["message"]
        assert data["file_path"] == "test.json"
        mock_path.unlink.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_new_file_not_exists(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a new file that doesn't exist on disk"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink.side_effect = FileNotFoundError("File not found")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 404
        assert "Untracked file not found for deletion" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_new_file_os_error(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a new file with OSError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink.side_effect = OSError("Permission denied")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 500
        assert "Failed to delete untracked file" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_deleted_file(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test restoring a deleted file from HEAD"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_DELETED

        # Mock HEAD commit and blob
        mock_blob = MagicMock()
        mock_blob.data = b"file content"
        mock_tree = MagicMock()
        mock_tree.__getitem__.return_value = mock_blob
        mock_commit = MagicMock()
        mock_commit.tree = mock_tree
        mock_repo.head.peel.return_value = mock_commit

        mock_path = MagicMock()
        mock_path.parent.mkdir.return_value = None
        mock_path.write_bytes.return_value = None

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Restored deleted file" in data["message"]
        mock_path.write_bytes.assert_called_once_with(b"file content")

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_deleted_file_not_in_head(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test restoring a deleted file that doesn't exist in HEAD"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_DELETED

        mock_tree = MagicMock()
        mock_tree.__getitem__.side_effect = KeyError("File not found")
        mock_commit = MagicMock()
        mock_commit.tree = mock_tree
        mock_repo.head.peel.return_value = mock_commit

        mock_path = MagicMock()

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 404
        assert "File not found in HEAD" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_modified_file(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding changes in a modified file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_MODIFIED

        # Mock HEAD commit and blob
        mock_blob = MagicMock()
        mock_blob.data = b"original content"
        mock_tree = MagicMock()
        mock_tree.__getitem__.return_value = mock_blob
        mock_commit = MagicMock()
        mock_commit.tree = mock_tree
        mock_repo.head.peel.return_value = mock_commit

        mock_path = MagicMock()
        mock_path.write_bytes.return_value = None

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Discarded changes in" in data["message"]
        mock_path.write_bytes.assert_called_once_with(b"original content")

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_staged_new_file(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a staged new file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_INDEX_NEW

        mock_index = MagicMock()
        mock_repo.index = mock_index

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.unlink.return_value = None

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Discarded staged changes" in data["message"]
        mock_index.remove.assert_called_once_with("test.json")
        mock_index.write.assert_called_once()
        mock_path.unlink.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_staged_modified_file(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a staged modified file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_INDEX_MODIFIED

        mock_index = MagicMock()
        mock_repo.index = mock_index

        # Mock HEAD commit and blob
        mock_blob = MagicMock()
        mock_blob.data = b"original content"
        mock_tree = MagicMock()
        mock_tree.__getitem__.return_value = mock_blob
        mock_commit = MagicMock()
        mock_commit.tree = mock_tree
        mock_repo.head.peel.return_value = mock_commit

        mock_path = MagicMock()
        mock_path.parent.mkdir.return_value = None
        mock_path.write_bytes.return_value = None

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", Path("/mock/repo")):
            with patch("pathlib.Path.__truediv__", return_value=mock_path):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Discarded staged changes" in data["message"]
        mock_index.remove.assert_called_once_with("test.json")
        mock_index.write.assert_called_once()
        mock_path.write_bytes.assert_called_once_with(b"original content")

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_file_not_found(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a file that doesn't exist in repository"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.side_effect = KeyError("File not found")

        response = await async_client.post("/git/discard", json={"file_path": "nonexistent.json"})

        assert response.status_code == 404
        assert "File not found in repository" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_file_no_changes(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discarding a file with no changes"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = 0  # No changes

        response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 400
        assert "File has no changes to discard" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_git_error(
        self, mock_repository_class, async_client, mock_get_current_user_admin, mock_is_admin_or_superuser_is_active
    ):
        """Test discard handling of GitError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.side_effect = GitError("Git error")

        response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 500
        assert "Git error" in response.json()["detail"]
