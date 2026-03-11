import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import datetime
from app.api.api_v1.endpoints import git_ops
from app.db.models.user import Role
from app.db.schemas.user import User

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


@pytest.fixture(autouse=True)
def mock_get_user_for_endpoints():
    mock_user = User(
        id=1,
        github_id=123,
        username="test_admin",
        email="test_admin@example.com",
        avatar_url="some_url.com",
        role=Role.ADMIN.value,
        created_on=datetime.datetime.utcnow(),
        last_login=datetime.datetime.utcnow(),
        is_active=True,
    )
    with patch("app.api.api_v1.endpoints.git_ops.get_user", return_value=mock_user) as mock_get_user:
        yield mock_get_user


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(async_client):
    response = await async_client.post(
        "/git/sync",
        headers={"x-hub-signature-256": "sha256=1234", "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid signature"}


@pytest.mark.asyncio
async def test_github_webhook_missing_signature_header(async_client):
    response = await async_client.post("/git/sync")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid signature"}


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature_format(async_client):
    response = await async_client.post(
        "/git/sync",
        headers={
            "x-hub-signature-256": "invalid-format",
            "Content-Type": "application/x-www-form-urlencoded",
        },
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

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.get_status_name")
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    @patch("app.api.api_v1.endpoints.git_ops.ensure_safe_directory")
    async def test_get_git_status_non_admin_exact_namespace_match(
        self,
        mock_ensure_safe,
        mock_repository_class,
        mock_get_status_name,
        async_client,
        mock_get_current_user,
        mock_is_admin_or_superuser_is_active,
    ):
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status.return_value = {
            "translation/en/joann/s1.json": GIT_STATUS_WT_MODIFIED,
            "translation/en/ann/s2.json": GIT_STATUS_WT_MODIFIED,
        }
        mock_get_status_name.return_value = "modified"

        non_admin_user = User(
            id=2,
            github_id=123,
            username="ann",
            email="ann@example.com",
            avatar_url="some_url.com",
            role=Role.WRITER.value,
            created_on=datetime.datetime.utcnow(),
            last_login=datetime.datetime.utcnow(),
            is_active=True,
        )

        with patch(
            "app.api.api_v1.endpoints.git_ops.get_user",
            return_value=non_admin_user,
        ):
            response = await async_client.get("/git/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["files"][0]["path"] == "translation/en/ann/s2.json"


# Tests for get_file_diff endpoint
class TestGetFileDiff:
    """Tests for GET /git/diff/{file_path} endpoint"""

    @pytest.mark.asyncio
    async def test_get_file_diff_unauthorized(self, async_client):
        """Test that unauthorized users cannot access file diff"""
        response = await async_client.get("/git/diff/test.json")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_new_file(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test diff for a new file"""
        mock_status = MagicMock(stdout="?? test.json\n")
        mock_diff = MagicMock(stdout="diff --git a/test.json b/test.json\n+line1\n")
        mock_run.side_effect = [mock_status, mock_diff]

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.json"
        assert data["status"] == "untracked"
        assert "+line1" in data["diff"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_no_changes(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Unchanged file should return 400 (no status output)."""
        mock_status = MagicMock(stdout="")
        mock_run.return_value = mock_status

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 400
        assert "File has no changes" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_deleted_file(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test diff for a deleted file"""
        mock_status = MagicMock(stdout=" D test.json\n")
        mock_diff = MagicMock(stdout="diff --git a/test.json b/test.json\n-deleted\n")
        mock_run.side_effect = [mock_status, mock_diff]

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.json"
        assert data["status"] == "deleted"
        assert "-deleted" in data["diff"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_modified_file_with_diff(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test diff for a modified file with diff content"""
        mock_status = MagicMock(stdout=" M test.json\n")
        mock_diff = MagicMock(
            stdout="diff --git a/test.json b/test.json\n-old line\n+new line"
        )
        mock_run.side_effect = [mock_status, mock_diff]

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.json"
        assert data["status"] == "modified"
        assert "diff --git" in data["diff"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_modified_file_no_diff(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Empty diff output is still a successful response with empty diff."""
        mock_status = MagicMock(stdout=" M test.json\n")
        mock_diff = MagicMock(stdout="")
        mock_run.side_effect = [mock_status, mock_diff]

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "modified"
        assert data["diff"] == ""

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_file_not_found(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Non-existing file in git status flow returns 400 (no changes)."""
        mock_status = MagicMock(stdout="")
        mock_run.return_value = mock_status

        response = await async_client.get("/git/diff/nonexistent.json")

        assert response.status_code == 400
        assert "File has no changes" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_no_changes(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test diff for a file with no changes"""
        mock_status = MagicMock(stdout="")
        mock_run.return_value = mock_status

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 400
        assert "File has no changes" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_git_error(
        self,
        mock_run,
        async_client,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Unexpected exception in diff flow returns 500."""
        mock_run.side_effect = Exception("Git error")

        response = await async_client.get("/git/diff/test.json")

        assert response.status_code == 500
        assert "Error generating diff" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.subprocess.run")
    async def test_get_file_diff_non_admin_rejects_substring_match(
        self,
        mock_subprocess_run,
        async_client,
        mock_get_current_user,
        mock_is_admin_or_superuser_is_active,
    ):
        non_admin_user = User(
            id=2,
            github_id=123,
            username="ann",
            email="ann@example.com",
            avatar_url="some_url.com",
            role=Role.WRITER.value,
            created_on=datetime.datetime.utcnow(),
            last_login=datetime.datetime.utcnow(),
            is_active=True,
        )

        with patch(
            "app.api.api_v1.endpoints.git_ops.get_user",
            return_value=non_admin_user,
        ):
            response = await async_client.get("/git/diff/translation/en/joann/s1.json")

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()
        mock_subprocess_run.assert_not_called()


def test_validate_file_path_returns_normalized_relative_path():
    normalized = git_ops._validate_file_path(
        "translation/en/ann/../ann/s1.json",
        Path("/tmp/repo"),
    )

    assert normalized == "translation/en/ann/s1.json"


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
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test discarding a new untracked file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW

        work_dir = tmp_path / "repo"
        work_dir.mkdir()
        file_path = work_dir / "test.json"
        file_path.write_text("temp")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Deleted untracked file" in data["message"]
        assert data["file_path"] == "test.json"
        assert not file_path.exists()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_new_file_not_exists(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test discarding a new file that doesn't exist on disk"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW

        work_dir = tmp_path / "repo"
        work_dir.mkdir()
        (work_dir / "test.json").write_text("temp")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            with patch("pathlib.Path.unlink", side_effect=FileNotFoundError("File not found")):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 404
        assert "Untracked file not found for deletion" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_new_file_os_error(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test discarding a new file with OSError"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_WT_NEW

        work_dir = tmp_path / "repo"
        work_dir.mkdir()
        (work_dir / "test.json").write_text("temp")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            with patch("pathlib.Path.unlink", side_effect=OSError("Permission denied")):
                response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 500
        assert "Failed to delete untracked file" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_deleted_file(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
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

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Restored deleted file" in data["message"]
        assert (work_dir / "test.json").read_bytes() == b"file content"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_deleted_file_not_in_head(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
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

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 404
        assert "File not found in HEAD" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_modified_file(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
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

        work_dir = tmp_path / "repo"
        work_dir.mkdir()
        (work_dir / "test.json").write_text("modified")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Discarded changes in" in data["message"]
        assert (work_dir / "test.json").read_bytes() == b"original content"

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_staged_new_file(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
    ):
        """Test discarding a staged new file"""
        mock_repo = MagicMock()
        mock_repository_class.return_value = mock_repo
        mock_repo.status_file.return_value = GIT_STATUS_INDEX_NEW

        mock_index = MagicMock()
        mock_repo.index = mock_index

        work_dir = tmp_path / "repo"
        work_dir.mkdir()
        file_path = work_dir / "test.json"
        file_path.write_text("temp")

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Discarded staged changes" in data["message"]
        mock_index.remove.assert_called_once_with("test.json")
        mock_index.write.assert_called_once()
        assert not file_path.exists()

    @pytest.mark.asyncio
    @patch("app.api.api_v1.endpoints.git_ops.Repository")
    async def test_discard_staged_modified_file(
        self,
        mock_repository_class,
        async_client,
        tmp_path,
        mock_get_current_user_admin,
        mock_is_admin_or_superuser_is_active,
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

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        with patch("app.api.api_v1.endpoints.git_ops.settings.WORK_DIR", work_dir):
            response = await async_client.post("/git/discard", json={"file_path": "test.json"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Discarded staged changes" in data["message"]
        mock_index.remove.assert_called_once_with("test.json")
        mock_index.write.assert_called_once()
        assert (work_dir / "test.json").read_bytes() == b"original content"

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
