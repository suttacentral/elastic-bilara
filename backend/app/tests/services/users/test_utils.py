import json
from unittest.mock import patch

import pytest
from app.core.config import settings
from app.services.users.utils import add_user_to_db, get_user, is_username_in_muid


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
