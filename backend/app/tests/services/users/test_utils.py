import json
from unittest.mock import patch

import pytest
from app.core.config import settings
from app.services.users.utils import (
    add_user_to_users_json,
    get_user,
    is_username_in_muid,
)


class TestUserUtils:
    @patch("app.services.users.utils.get_json_data")
    def test_get_user(self, mock_get_json_data, users, github_data) -> None:
        mock_get_json_data.return_value = [
            user.dict()
            for user in users(
                n=3,
                github_id=[1, 2, 3],
                username=["test", "test2", "test3"],
                role=["proofreader", "translator", "admin"],
                email=["test@test.com", "test2@test.com", "test3@test.com"],
            )
        ]

        user = get_user(github_data(github_id=1, username="test", email="test@test.com")["github_id"])

        assert user.github_id == 1
        assert user.username == "test"
        assert user.role == "proofreader"
        assert user.email == "test@test.com"

        user = get_user(github_data(github_id=2, username="test2", email="test2@test.com")["github_id"])
        assert user.github_id == 2
        assert user.username == "test2"
        assert user.role == "translator"
        assert user.email == "test2@test.com"

        user = get_user(github_data(github_id=3, username="test3", email="test3@test.com")["github_id"])
        assert user.github_id == 3
        assert user.username == "test3"
        assert user.role == "admin"
        assert user.email == "test3@test.com"

    @patch("app.services.users.utils.get_json_data")
    def test_get_user_invalid_id(self, mock_get_json_data, users, github_data) -> None:
        mock_get_json_data.return_value = [user.dict() for user in users(n=3)]

        with pytest.raises(IndexError):
            get_user(github_data(github_id=-1)["github_id"])

        with pytest.raises(IndexError):
            get_user(github_data(github_id=0)["github_id"])

        with pytest.raises(IndexError):
            get_user(github_data(github_id=4)["github_id"])

        with pytest.raises(IndexError):
            get_user(github_data(github_id="invalid")["github_id"])

    @patch("app.services.users.utils.get_json_data")
    def test_get_user_file_does_not_exist(self, mock_get_json_data, github_data) -> None:
        mock_get_json_data.side_effect = FileNotFoundError

        with pytest.raises(FileNotFoundError):
            get_user(github_data()["github_id"])

    @patch("app.services.users.utils.get_json_data")
    def test_get_user_user_data_corrupted(self, mock_get_json_data, github_data) -> None:
        mock_get_json_data.side_effect = KeyError
        with pytest.raises(KeyError):
            get_user(github_data()["github_id"])

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

    @pytest.mark.users_file(
        [
            {
                "github_id": 1,
                "username": "test",
                "email": "test@test.com",
                "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                "role": "translator",
            },
            {
                "github_id": 2,
                "username": "test2",
                "email": "test2@test.com",
                "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                "role": "translator",
            },
        ]
    )
    @pytest.mark.parametrize(
        "user_data, expected_result",
        [
            (
                {
                    "github_id": 1,
                    "username": "test",
                    "email": "test@test.com",
                    "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                },
                (
                    False,
                    {
                        "github_id": 1,
                        "username": "test",
                        "email": "test@test.com",
                        "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                        "role": "translator",
                    },
                ),
            ),
            (
                {
                    "username": "test",
                    "email": "test@test.com",
                    "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                },
                (False, None),
            ),
            (
                {
                    "github_id": 3,
                    "username": "new_user",
                    "email": "new_user@test.com",
                    "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                },
                (
                    True,
                    {
                        "github_id": 3,
                        "username": "new_user",
                        "email": "new_user@test.com",
                        "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                        "role": "proofreader",
                    },
                ),
            ),
        ],
    )
    @patch("app.services.users.utils.get_json_data")
    @patch("app.services.users.utils.get_user")
    def test_add_user_to_users_json(
        self,
        mock_get_user,
        mock_get_json_data,
        user_data,
        expected_result,
        users_file,
    ) -> None:
        settings.USERS_FILE = users_file
        mock_get_json_data.return_value = json.loads(settings.USERS_FILE.read_text())
        mock_get_user.return_value = {
            **user_data,
            "role": "proofreader" if user_data.get("github_id") == 3 else "translator",
        }

        result = add_user_to_users_json(user_data)
        assert result == expected_result

    @pytest.mark.users_file([])
    @pytest.mark.parametrize(
        "user_data, expected_result",
        [
            (
                {
                    "github_id": 1,
                    "username": "test",
                    "email": "test@test.com",
                    "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                },
                (
                    True,
                    {
                        "github_id": 1,
                        "username": "test",
                        "email": "test@test.com",
                        "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
                        "role": "proofreader",
                    },
                ),
            ),
        ],
    )
    @patch("app.services.users.utils.get_json_data")
    @patch("app.services.users.utils.get_user")
    def test_add_user_to_empty_users_json(
        self,
        mock_get_user,
        mock_get_json_data,
        user_data,
        expected_result,
        users_file,
    ) -> None:
        settings.USERS_FILE = users_file
        mock_get_json_data.return_value = json.loads(settings.USERS_FILE.read_text())

        mock_get_user.return_value = {
            "github_id": user_data.get("github_id"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "avatar_url": user_data.get("avatar_url"),
            "role": "proofreader",
        }

        result = add_user_to_users_json(user_data)
        assert result == expected_result
