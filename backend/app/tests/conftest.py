import json

import pytest
import pytest_asyncio
from app.core.config import settings
from app.main import app
from app.services.users.roles import Role
from app.services.users.schema import UserData
from app.tests.services.users.factories import UserFactory
from app.tests.utils.factories import ProjectFactory, PublicationFactory
from httpx import AsyncClient


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        app=app,
        base_url=f"{settings.SERVER_HOST}:{settings.DOCKER_BACKEND_PORT}{settings.API_V1_STR}",
    ) as ac:
        yield ac


@pytest.fixture()
def users():
    def _users(n=3, **kwargs):
        return UserFactory.create_users(n, **kwargs)

    return _users


@pytest.fixture()
def user(github_data):
    return UserData(**github_data(), role=Role.TRANSLATOR.value)


@pytest.fixture()
def project():
    def _project(**kwargs):
        return ProjectFactory.create_project(**kwargs)

    return _project


@pytest.fixture()
def projects():
    def _projects(n=1, **kwargs):
        return ProjectFactory.create_projects(n, **kwargs)

    return _projects


@pytest.fixture()
def publications():
    def _publications(n=1, **kwargs):
        return PublicationFactory.create_publications(n, **kwargs)

    return _publications


@pytest.fixture()
def muids():
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
def github_data():
    def _github_data(
        github_id=1,
        username="test",
        email="test@test.com",
        avatar_url="https://avatars.githubusercontent.com/u/123?v=4",
    ):
        return {
            "github_id": github_id,
            "username": username,
            "email": email,
            "avatar_url": avatar_url,
        }

    return _github_data


@pytest.fixture
def users_file(tmp_path, request):
    file = tmp_path / "test_users.json"
    users_mareker = request.node.get_closest_marker("users_file")
    if users_mareker:
        users = users_mareker.args[0]
        file.write_text(json.dumps(users))
    return file
