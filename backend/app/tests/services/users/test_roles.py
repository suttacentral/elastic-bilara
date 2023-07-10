from unittest.mock import patch

import pytest
from app.services.users.roles import Role, add_role, get_role
from app.services.users.schema import UserData
from app.services.users.utils import get_user
from pydantic import ValidationError


class TestUserRoles:
    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_all_data_present(
        self, mock_creator_in_list, mock_find_unique_data, muids, github_data
    ) -> None:
        mock_find_unique_data.return_value = muids
        mock_creator_in_list.side_effect = [True, True]
        data = github_data()
        assert add_role(data) == UserData(**data, role=Role.TRANSLATOR.value)

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_data_only_in_muids(
        self, mock_creator_in_list, mock_find_unique_data, muids, github_data
    ) -> None:
        mock_find_unique_data.return_value = muids
        mock_creator_in_list.side_effect = [False, False]
        data = github_data()
        assert add_role(data) == UserData(**data, role=Role.TRANSLATOR.value)

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_data_only_in_projects(
        self, mock_creator_in_list, mock_find_unique_data, github_data
    ) -> None:
        mock_find_unique_data.return_value = []
        mock_creator_in_list.side_effect = [True, False]
        data = github_data()
        assert add_role(data) == UserData(**data, role=Role.TRANSLATOR.value)

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_data_only_in_publication(
        self, mock_creator_in_list, mock_find_unique_data, github_data
    ) -> None:
        mock_find_unique_data.return_value = []
        mock_creator_in_list.side_effect = [False, True]
        data = github_data()
        assert add_role(data) == UserData(**data, role=Role.TRANSLATOR.value)

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_no_data_in_muid_projects_publications(
        self, mock_creator_in_list, mock_find_unique_data, github_data
    ) -> None:
        mock_find_unique_data.return_value = []
        mock_creator_in_list.side_effect = [False, False]
        data = github_data()
        assert add_role(data) == UserData(**data, role=Role.PROOFREADER.value)

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_empty_user_data(self, mock_creator_in_list, mock_find_unique_data, muids) -> None:
        mock_find_unique_data.return_value = muids
        mock_creator_in_list.side_effect = [True, True]
        with pytest.raises(ValidationError):
            add_role({})

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_no_username_in_user_data(
        self, mock_creator_in_list, mock_find_unique_data, muids, github_data
    ) -> None:
        mock_find_unique_data.return_value = muids
        mock_creator_in_list.side_effect = [True, True]
        data = github_data()
        del data["username"]
        with pytest.raises(ValidationError):
            add_role(data)

    @patch("app.services.users.roles.search.find_unique_data")
    @patch("app.services.users.roles.utils.check_creator_github_handle_in_list")
    def test_add_role_with_none_as_username_in_user_data(
        self, mock_creator_in_list, mock_find_unique_data, muids, github_data
    ) -> None:
        mock_find_unique_data.return_value = muids
        mock_creator_in_list.side_effect = [True, True]
        data = github_data()
        data["username"] = None
        with pytest.raises(ValidationError):
            add_role(data)

    @patch("app.services.users.utils.get_json_data")
    def test_get_role(self, mock_get_json_data, github_data, users) -> None:
        users_data = users(n=3, github_id=[1, 2, 3], role=["proofreader", "translator", "admin"])
        mock_get_json_data.return_value = [user.dict() for user in users_data]
        user = get_user(github_data(github_id=1)["github_id"])
        assert user.role == users_data[0].role
        user = get_user(github_data(github_id=2)["github_id"])
        assert user.role == users_data[1].role
        user = get_user(github_data(github_id=3)["github_id"])
        assert user.role == users_data[2].role

    @patch("app.services.users.utils.get_user")
    def test_get_role_user_does_not_exist(self, mock_get_user) -> None:
        mock_get_user.side_effect = IndexError
        with pytest.raises(IndexError):
            get_role(-1)

    @patch("app.services.users.roles.utils.get_user")
    def test_get_role_incorrect_role(self, mock_get_user, user) -> None:
        user_data = user
        user_data.role = "invalid"
        mock_get_user.return_value = user_data

        role = get_role(user.github_id)
        assert role != "proofreader"
