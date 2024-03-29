import datetime
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Generator, Iterator
from unittest.mock import MagicMock, Mock, create_autospec, patch

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from app.core.config import settings
from app.core.text_types import TextType
from app.db.models.user import Role
from app.db.models.user import User as mUser
from app.db.schemas.user import User, UserBase
from app.main import app
from app.services.auth import utils
from app.services.auth.schema import TokenData
from app.services.directories.remover import Remover
from app.services.directories.utils import validate_path
from app.services.git.manager import GitManager
from app.services.projects.uid_reducer import UIDReducer
from app.services.users import permissions
from app.tests.services.users.factories import UserFactory
from app.tests.utils.factories import ProjectFactory, PublicationFactory
from app.tests.utils.git import create_repo_structure_with_content
from httpx import AsyncClient
from pygit2 import Commit, Repository, Signature, init_repository
from sqlalchemy.orm import Session


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


@pytest.fixture
def mock_get_current_user_admin(user: UserBase) -> Generator[None, Any, None]:
    user.role = Role.ADMIN.value

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


@pytest.fixture()
def mock_path_obj() -> Callable[[bool, str], MagicMock]:
    def _mock_path_obj(is_dir_value: bool, return_value: str):
        mock_path = MagicMock()
        mock_path.is_dir = Mock(return_value=is_dir_value)
        mock_path.exists = Mock(return_value=is_dir_value)
        mock_path.relative_to = Mock(return_value=return_value)
        mock_path.name = return_value
        mock_path.__str__ = Mock(return_value=return_value)
        return mock_path

    return _mock_path_obj


@pytest.fixture
def mock_paths(mocker) -> Callable[[dict[str, list[Path]]], MagicMock]:
    def _mock_paths(custom_paths: dict[str, list[Path]]) -> MagicMock:
        mock_rglob = mocker.patch.object(Path, "rglob", autospec=True)

        full_paths = {text_type.value: [] for text_type in TextType}
        full_paths.update(custom_paths)

        def side_effect(self, arg1: str) -> Iterator[Path]:
            if arg1 == "*":
                text_type = str(self).split("/")[-1]
                return iter(full_paths.get(text_type, []))
            return iter([])

        mock_rglob.side_effect = side_effect
        return mock_rglob

    return _mock_paths


@pytest.fixture
def mock_path_exists(mocker):
    mock_exists = mocker.patch.object(Path, "exists", autospec=True)

    def _mock_exists(paths):
        all_existing_paths = []
        for path in paths:
            helper_path = Path()
            for part in path.parts:
                helper_path /= part
                all_existing_paths.append(helper_path)

        def exists_side_effect(self):
            return self in all_existing_paths

        mock_exists.side_effect = exists_side_effect

    return _mock_exists


@pytest.fixture
def mock_session():
    with patch("app.db.database.SessionLocal") as mock_session_local:
        mock_session = create_autospec(Session, instance=True)
        mock_session_local.return_value = mock_session
        mock_session.commit.return_value = None
        yield mock_session


@pytest.fixture
def mock_user(
    id_: int = 1,
    github_id: int = 123,
    username: str = "test_user",
    email: str = "test@email.com",
    avatar_url: str = "example.com/url",
    role: Role = Role.REVIEWER.value,
    is_active: bool = True,
    remarks: list = None,
):
    return mUser(
        id=id_,
        github_id=github_id,
        username=username,
        email=email,
        avatar_url=avatar_url,
        role=role,
        created_on=datetime.datetime.utcnow(),
        last_login=datetime.datetime.utcnow(),
        is_active=is_active,
        remarks=remarks if remarks else [],
    )


@pytest.fixture
def mock_users():
    return [
        User(
            id=1,
            github_id=123,
            username="test_user",
            email="test@example.com",
            avatar_url="some_url.com",
            role="reviewer",
            created_on=datetime.datetime.utcnow(),
            last_login=datetime.datetime.utcnow(),
            is_active=True,
            remarks=[],
        ),
        User(
            id=2,
            github_id=12345,
            username="test_user_2",
            email="testtesttest@example.com",
            avatar_url="some_url.com",
            role="writer",
            created_on=datetime.datetime.utcnow(),
            last_login=datetime.datetime.utcnow(),
            is_active=True,
            remarks=[],
        ),
    ]


@pytest.fixture
def mock_is_admin_or_superuser_is_active(mock_user: User) -> Generator[None, Any, None]:
    async def override_dependency():
        return False

    app.dependency_overrides[permissions.is_admin_or_superuser] = override_dependency
    app.dependency_overrides[permissions.is_user_active] = override_dependency

    yield
    app.dependency_overrides = {}


@pytest.fixture
def mock_path_iterdir():
    with patch("pathlib.Path.iterdir") as mock_iterdir:
        mock_iterdir.return_value = [
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.1_root-pli-ms.json"),
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.2_root-pli-ms.json"),
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.3_root-pli-ms.json"),
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.4_root-pli-ms.json"),
            Path("checkouts/published/root/pli/ms/abhidhamma/ds/ds1/ds1.5_root-pli-ms.json"),
        ]
        yield mock_iterdir


@pytest.fixture
def mock_create_new_project(mocker):
    delay_return = MagicMock()
    delay_return.id = "test_task_id"

    mocker.patch("app.api.api_v1.endpoints.projects.create_project_file", return_value=True)
    mocker.patch("search.search.Search.update_indexes", return_value=None)
    mocker.patch("app.tasks.commit.delay", return_value=delay_return)


@pytest.fixture
def mock_new_project_create_data(mocker, mock_user):
    mocker.patch(
        "app.api.api_v1.endpoints.projects.create_new_project_file_names",
        return_value=[
            (
                Path(
                    f"/app/checkouts/unpublished/translation/en/{mock_user.username}/sutta/an/an1/an1.1-10_translation-en-{mock_user.username}.json"
                ),
                Path(
                    f"/app/checkouts/unpublished/comment/en/{mock_user.username}/sutta/an/an1/an1.1-10_comment-en-{mock_user.username}.json"
                ),
            ),
            (
                Path(
                    f"/app/checkouts/unpublished/translation/en/{mock_user.username}/sutta/an/an1/an1.11-20_translation-en-{mock_user.username}.json"
                ),
                Path(
                    f"/app/checkouts/unpublished/comment/en/{mock_user.username}/sutta/an/an1/an1.11-20_comment-en-{mock_user.username}.json"
                ),
            ),
        ],
    )
    mocker.patch(
        "search.utils.get_json_data",
        side_effect=[{"an1.1:0.1": "Test", "an1.1:0.2": "Test2"}, {"an1.11:0.1": "Test", "an1.11:0.2": "Test2"}],
    )

    def glb():
        paths = [
            Path("checkouts/published/root/pli/ms/sutta/an/an1/an1.1-10_root-pli-ms.json"),
            Path("checkouts/published/root/pli/ms/sutta/an/an1/an1.11-20_root-pli-ms.json"),
        ]
        yield from paths

    mocker.patch(
        "pathlib.Path.glob",
        return_value=glb(),
    )
    mocker.patch("pathlib.Path.is_dir", return_value=False)


@pytest.fixture
def remover(mocker, user) -> Callable[[Path], tuple[Remover, MagicMock, MagicMock, MagicMock, MagicMock]]:
    mock_remove_from_elastic = mocker.patch("app.services.directories.remover.Remover._remove_from_elastic")
    mock_remove_commit = mocker.patch("app.services.directories.remover.Remover._remove_commit")
    mock_delete_elements = mocker.patch("app.services.directories.remover.Remover._delete_elements")
    mock_get_paths = mocker.patch("app.services.directories.remover.Remover._get_paths")
    mock_get_matches = mocker.patch("app.services.directories.utils.get_matches")
    mock_get_matches_method = mocker.patch("app.services.directories.remover.Remover._get_matches")

    def _remover(path: Path):
        remover = Remover(user, path)
        return (
            remover,
            mock_remove_from_elastic,
            mock_remove_commit,
            mock_delete_elements,
            mock_get_paths,
            mock_get_matches,
            mock_get_matches_method,
        )

    return _remover


@pytest.fixture
def uid_reducer(mocker, user) -> Callable[[Path, list[str], bool], tuple[UIDReducer, MagicMock, MagicMock]]:
    mock_reduce_commit = mocker.patch("app.services.projects.uid_reducer.UIDReducer._reduce_commit")
    mock_get_matches = mocker.patch("app.services.directories.utils.get_matches")

    def _uid_reducer(path: Path, uids: list[str], exact: bool = False, get_matches_value=set()):
        mock_get_matches.return_value = get_matches_value
        uid_reducer = UIDReducer(user, path, uids, exact)
        uid_reducer.related_paths = get_matches_value
        return uid_reducer, mock_reduce_commit, mock_get_matches

    return _uid_reducer


@pytest.fixture
def mock_validate_path() -> Generator[None, Any, None]:
    async def _mock_validate_path_function(path: str) -> Path:
        return settings.WORK_DIR / path

    app.dependency_overrides[validate_path] = _mock_validate_path_function
    yield
    app.dependency_overrides = {}
