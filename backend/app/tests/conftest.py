import json
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Generator

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from app.core.config import settings
from app.db.models.user import Role
from app.db.schemas.user import UserBase
from app.main import app
from app.services.auth import utils
from app.services.auth.schema import TokenData
from app.services.git.manager import GitManager
from app.tests.services.users.factories import UserFactory
from app.tests.utils.factories import ProjectFactory, PublicationFactory
from app.tests.utils.git import create_repo_structure_with_content
from httpx import AsyncClient
from pygit2 import Commit, Repository, Signature, init_repository


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        app=app,
        base_url=f"{settings.SERVER_BACKEND_HOST}:{settings.DOCKER_BACKEND_PORT}{settings.API_V1_STR}",
    ) as ac:
        yield ac


@pytest.fixture()
def users() -> Callable[[int, dict[str, Any]], list[UserBase]]:
    def _users(n=3, **kwargs) -> list[UserBase]:
        return UserFactory.create_users(n, **kwargs)

    return _users


@pytest.fixture()
def user(github_data) -> UserBase:
    return UserBase(**github_data(), role=Role.WRITER.value)


@pytest.fixture()
def project() -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _project(**kwargs):
        return ProjectFactory.create_project(**kwargs)

    return _project


@pytest.fixture()
def projects() -> Callable[[int, dict[str, Any]], list[dict[str, Any]]]:
    def _projects(n=1, **kwargs):
        return ProjectFactory.create_projects(n, **kwargs)

    return _projects


@pytest.fixture()
def publications() -> Callable[[int, dict[str, Any]], list[dict[str, Any]]]:
    def _publications(n=1, **kwargs):
        return PublicationFactory.create_publications(n, **kwargs)

    return _publications


@pytest.fixture()
def muids() -> list[str]:
    return [
        "translation-en-test",
        "translation-en-test2",
        "root-pli-test",
        "html-en-test",
        "reference-en-test",
        "variant-en-test",
        "comment-en-test",
    ]


@pytest.fixture
def github_data() -> Callable[[int, str, str, str], dict[str, Any]]:
    def _github_data(
        github_id=1,
        username="test",
        email="test@test.com",
        avatar_url="https://avatars.githubusercontent.com/u/123?v=4",
    ) -> dict[str, Any]:
        return {
            "github_id": github_id,
            "username": username,
            "email": email,
            "avatar_url": avatar_url,
        }

    return _github_data


@pytest.fixture
def users_file(tmp_path: Path, request: type[FixtureRequest]) -> Path:
    file: Path = tmp_path / "test_users.json"
    users_mareker: Any = request.node.get_closest_marker("users_file")
    if users_mareker:
        users = users_mareker.args[0]
        file.write_text(json.dumps(users))
    return file


@pytest.fixture
def mock_get_current_user(user: UserBase) -> Generator[None, Any, None]:
    async def _mock_get_current_user_function() -> TokenData:
        return TokenData(github_id=str(user.github_id), username=user.username)

    app.dependency_overrides[utils.get_current_user] = _mock_get_current_user_function
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def setup_git_repos(tmpdir):
    """Creates temporary Git repositories for testing."""
    published_dir = tmpdir / "published"
    unpublished_dir = tmpdir / "unpublished"
    remote_dir = tmpdir / "remote"

    init_repository(str(published_dir))
    init_repository(str(unpublished_dir))
    remote_repo = init_repository(str(remote_dir))

    create_repo_structure_with_content(published_dir)
    create_repo_structure_with_content(unpublished_dir)
    create_repo_structure_with_content(remote_dir)

    author = committer = Signature("Test", "test@test.com")

    for branch_name in ["published", "unpublished"]:
        index = remote_repo.index
        index.add_all()
        index.write()
        tree = index.write_tree()
        if remote_repo.is_empty:
            remote_repo.create_commit("HEAD", author, committer, f"Initial commit in {branch_name}", tree, [])
            remote_repo.create_branch(branch_name, remote_repo.head.peel(Commit))
        else:
            remote_repo.create_commit(
                "HEAD",
                author,
                committer,
                f"Additional commit in {branch_name}",
                tree,
                [remote_repo.head.peel(Commit).id],
            )
            remote_repo.create_branch(branch_name, remote_repo.head.peel(Commit))

    for repo_dir, branch_name in [(published_dir, "published"), (unpublished_dir, "unpublished")]:
        repo = Repository(str(repo_dir))

        if repo.is_empty:
            index = repo.index
            index.add_all()
            index.write()
            tree = index.write_tree()
            repo.create_commit("HEAD", author, committer, "Initial commit", tree, [])

        if "origin" not in repo.remotes:
            repo.remotes.create("origin", str(remote_dir))
        repo.create_branch(branch_name, repo.head.peel(Commit))
        repo.create_reference(f"refs/remotes/origin/{branch_name}", repo.head.peel(Commit).id)

    return published_dir, unpublished_dir, remote_dir


@pytest.fixture
def git_manager(setup_git_repos, user):
    """Provides an instance of the GitManager class for testing."""
    published_dir, unpublished_dir, _ = setup_git_repos
    return GitManager(published_dir, unpublished_dir, user)
