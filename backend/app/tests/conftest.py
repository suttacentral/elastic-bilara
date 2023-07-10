import json
from pathlib import Path
from typing import Any, AsyncGenerator, Callable

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from app.core.config import settings
from app.main import app
from app.services.auth import utils
from app.services.auth.schema import TokenData
from app.services.users.roles import Role
from app.services.users.schema import UserData
from app.tests.services.users.factories import UserFactory
from app.tests.utils.factories import ProjectFactory, PublicationFactory
from httpx import AsyncClient


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        app=app,
        base_url=f"{settings.SERVER_BACKEND_HOST}:{settings.DOCKER_BACKEND_PORT}{settings.API_V1_STR}",
    ) as ac:
        yield ac


@pytest.fixture()
def users() -> Callable[[int, dict[str, Any]], list[UserData]]:
    def _users(n=3, **kwargs) -> list[UserData]:
        return UserFactory.create_users(n, **kwargs)

    return _users


@pytest.fixture()
def user(github_data) -> UserData:
    return UserData(**github_data(), role=Role.TRANSLATOR.value)


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
def mock_get_current_user(user: UserData) -> Generator[None, Any, None]:
    async def _mock_get_current_user_function() -> TokenData:
        return TokenData(github_id=str(user.github_id), username=user.username)

    app.dependency_overrides[utils.get_current_user] = _mock_get_current_user_function
    yield
    app.dependency_overrides = {}
