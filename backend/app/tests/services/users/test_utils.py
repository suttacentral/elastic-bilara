import datetime

import pytest
from app.db.models.user import User as mUser
from app.db.schemas.user import User
from app.services.users.utils import (
    add_user_to_db,
    get_roles,
    get_user,
    is_user_active,
    is_username_in_muid,
    update_user,
)
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError


class TestUserUtils:
    def test_is_user_in_muid_valid(self) -> None:
        assert is_username_in_muid("username", "translation-en-username")

    def test_is_user_in_muid_invalid(self) -> None:
        assert not is_username_in_muid("username", "translation-en-test")
        assert not is_username_in_muid("username", "translation-en-USERNAME")
        assert not is_username_in_muid("username", "")
        assert not is_username_in_muid("", "translation-en-username")

    def test_check_creator_github_handle_in_list(self, github_data, projects, publications) -> None:
        username = github_data()["username"]
        assert any(username in project["creator_github_handle"] for project in projects(creator_github_handle=username))
        assert any(
            username in publication["creator_github_handle"]
            for publication in publications(creator_github_handle=username)
        )

    def test_check_creator_github_handle_not_in_list(self, github_data, projects, publications) -> None:
        username = github_data(username="invalid")["username"]
        assert not any(username in project["creator_github_handle"] for project in projects())
        assert not any(username in publication["creator_github_handle"] for publication in publications())


@pytest.mark.parametrize(
    "id_, github_id, username, email, avatar_url, role, is_active",
    [
        (1, 123, "test_user", "test@example.com", None, "reviewer", True),
        (2, 1234, "second_user", "second@example.com", "http://example.com/avatar2", "contributor", False),
    ],
)
def test_get_user_with_mocked_db_session(mock_session, id_, github_id, username, email, avatar_url, role, is_active):
    mock_session.query.return_value.filter.return_value.first.return_value = mUser(
        id=id_,
        github_id=github_id,
        username=username,
        email=email,
        avatar_url=avatar_url,
        role=role,
        is_active=is_active,
        created_on=datetime.datetime.utcnow(),
        last_login=datetime.datetime.utcnow(),
        remarks=[],
    )

    result_user = get_user(github_id=github_id)

    assert isinstance(result_user, User)
    assert result_user.github_id == github_id
    assert result_user.id == id_
    assert result_user.username == username
    assert result_user.email == email
    assert result_user.avatar_url == avatar_url
    assert result_user.role == role
    assert result_user.is_active == is_active


def test_is_user_active(mock_user):
    assert is_user_active(mock_user)


def test_is_user_not_active(mock_user):
    mock_user.is_active = False
    assert not is_user_active(mock_user)


def test_get_roles():
    assert get_roles() == ["administrator", "superuser", "writer", "reviewer"]


def test_update_user_role_update(mock_session, mock_user):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user

    user_data = {
        "id": mock_user.id,
        "github_id": mock_user.github_id,
        "username": mock_user.username,
        "email": mock_user.email,
        "avatar_url": mock_user.avatar_url,
        "role": "administrator",
        "is_active": mock_user.is_active,
        "created_on": mock_user.created_on,
        "last_login": mock_user.last_login,
        "remarks": [],
    }
    assert mock_user.role == "reviewer"
    result_user = update_user(user_data)

    assert isinstance(result_user, User)
    assert result_user.role == "administrator"
    assert result_user.github_id == mock_user.github_id
    assert result_user.id == mock_user.id
    assert result_user.username == mock_user.username
    assert result_user.email == mock_user.email
    assert result_user.avatar_url == mock_user.avatar_url
    assert result_user.is_active == mock_user.is_active


def test_update_user_github_id_not_found(mock_session, mock_user):
    mock_session.query.return_value.filter.return_value.first.return_value = None

    user_data = {
        "id": mock_user.id,
        "github_id": 66666,
        "username": mock_user.username,
        "email": mock_user.email,
        "avatar_url": mock_user.avatar_url,
        "role": mock_user.role,
        "is_active": mock_user.is_active,
        "created_on": mock_user.created_on,
        "last_login": mock_user.last_login,
        "remarks": [],
    }

    with pytest.raises(HTTPException):
        update_user(user_data)


def test_update_user_id_update_fail_integrity_error(mock_session, mock_user):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.commit.side_effect = IntegrityError(None, None, None)
    user_data = {
        "id": 1,
        "github_id": 123456,  # unique identifier which update_user uses to find the user
        "username": mock_user.username,
        "email": mock_user.email,
        "avatar_url": mock_user.avatar_url,
        "role": mock_user.role,
        "is_active": mock_user.is_active,
        "created_on": mock_user.created_on,
        "last_login": mock_user.last_login,
        "remarks": [],
    }

    with pytest.raises(HTTPException):
        update_user(user_data)


def test_update_user_non_existing_attribute(mock_session, mock_user):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.commit.side_effect = ValueError
    user_data = {
        "id": mock_user.id,
        "github_id": mock_user.github_id,
        "username": mock_user.username,
        "email": mock_user.email,
        "avatar_url": mock_user.avatar_url,
        "role": mock_user.role,
        "is_active": mock_user.is_active,
        "created_on": mock_user.created_on,
        "last_login": mock_user.last_login,
        "remarks": [],
        "non_existing": "attribute",
    }

    with pytest.raises(ValueError):
        update_user(user_data)
