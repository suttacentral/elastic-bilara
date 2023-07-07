from unittest.mock import patch

import pytest
from app.services.users.permissions import can_edit_translation, owns_project
from app.services.users.roles import Role


class TestUserPermissions:
    def test_owns_project_valid_muid(self, user, project):
        project = project(creator_github_handle=user.username)
        assert owns_project(user.username, project, project["translation_muids"])

    def test_owns_project_invalid_muid(self, user, project):
        project = project(creator_github_handle=user.username)
        assert not owns_project(user.username, project, "invalid-muid")

    def _test_owns_project_invalid_creator_handle(self, user, project):
        project = project()
        assert not owns_project(user.username, project, project["translation_muids"])

    @pytest.mark.parametrize(
        "role, expected",
        [
            (Role.ADMIN.value, True),
            (Role.PROOFREADER.value, False),
        ],
    )
    @patch("app.services.users.permissions.get_user")
    def test_can_edit_translation_based_on_role(self, mock_get_user, user, muids, role, expected):
        user.role = role
        mock_get_user.return_value = user

        assert can_edit_translation(user.github_id, muids[0]) == expected

    @patch("app.services.users.permissions.get_user")
    @patch("app.services.users.permissions.is_username_in_muid")
    def test_can_edit_translation_username_in_muid(self, mock_is_user_in_muid, mock_get_user, user, muids):
        mock_is_user_in_muid.return_value = True
        mock_get_user.return_value = user
        assert can_edit_translation(user.github_id, muids[0])

    @pytest.mark.parametrize(
        "owns_project_return_value, expected",
        [
            (True, True),
            (False, False),
        ],
    )
    @patch("app.services.users.permissions.get_user")
    @patch("app.services.users.permissions.is_username_in_muid")
    @patch("app.services.users.permissions.get_json_data")
    @patch("app.services.users.permissions.owns_project")
    def test_can_edit_translation_user_is_translator(
        self,
        mock_owns_project,
        mock_get_json_data,
        mock_is_user_in_muid,
        mock_get_user,
        user,
        muids,
        projects,
        owns_project_return_value,
        expected,
    ):
        mock_owns_project.return_value = owns_project_return_value
        mock_is_user_in_muid.return_value = False
        mock_get_user.return_value = user
        mock_get_json_data.return_value = projects()

        assert can_edit_translation(user.github_id, muids[0]) == expected