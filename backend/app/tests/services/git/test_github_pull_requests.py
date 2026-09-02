from types import SimpleNamespace
from unittest.mock import Mock

from app.services.git.github_pull_requests import GithubPullRequests


def test_list_open_pull_requests_loads_repository_once_and_indexes_by_head():
    repository_identity = SimpleNamespace(full_name="suttacentral/bilara-data")
    first = SimpleNamespace(
        head=SimpleNamespace(
            ref="translation_en_test_sutta_an", repo=repository_identity
        )
    )
    second = SimpleNamespace(
        head=SimpleNamespace(
            ref="translation_en_test_sutta_sn", repo=repository_identity
        )
    )
    repository = Mock()
    repository.get_pulls.return_value = [first, second]
    github = Mock()
    github.get_repo.return_value = repository
    pull_requests = GithubPullRequests(github, "suttacentral/bilara-data")

    result = pull_requests.list_open()

    assert result == {
        "translation_en_test_sutta_an": first,
        "translation_en_test_sutta_sn": second,
    }
    github.get_repo.assert_called_once_with("suttacentral/bilara-data", lazy=True)
    repository.get_pulls.assert_called_once_with(state="open", base="published")


def test_list_open_ignores_same_named_branch_from_fork():
    owned = SimpleNamespace(
        head=SimpleNamespace(
            ref="translation_en_test_sutta_an",
            repo=SimpleNamespace(full_name="suttacentral/bilara-data"),
        )
    )
    forked = SimpleNamespace(
        head=SimpleNamespace(
            ref="translation_en_test_sutta_an",
            repo=SimpleNamespace(full_name="contributor/bilara-data"),
        )
    )
    repository = Mock()
    repository.get_pulls.return_value = [owned, forked]
    github = Mock()
    github.get_repo.return_value = repository
    pull_requests = GithubPullRequests(github, "suttacentral/bilara-data")

    result = pull_requests.list_open()

    assert result == {"translation_en_test_sutta_an": owned}


def test_list_open_ignores_pull_request_whose_source_repository_was_deleted():
    deleted_fork = SimpleNamespace(
        head=SimpleNamespace(ref="translation_en_test_sutta_an", repo=None)
    )
    repository = Mock()
    repository.get_pulls.return_value = [deleted_fork]
    github = Mock()
    github.get_repo.return_value = repository
    pull_requests = GithubPullRequests(github, "suttacentral/bilara-data")

    result = pull_requests.list_open()

    assert result == {}


def test_create_pull_request_returns_created_pull_request():
    repository = Mock()
    created_pull_request = Mock(html_url="https://github.com/example/pull/1")
    repository.create_pull.return_value = created_pull_request
    github = Mock()
    github.get_repo.return_value = repository
    pull_requests = GithubPullRequests(github, "suttacentral/bilara-data")

    result = pull_requests.create(
        title="New translations",
        body="Request body",
        head="suttacentral:translation_en_test_sutta_an",
    )

    assert result is created_pull_request
    repository.create_pull.assert_called_once_with(
        title="New translations",
        body="Request body",
        base="published",
        head="suttacentral:translation_en_test_sutta_an",
    )


def test_close_pull_request_closes_the_supplied_request():
    repository = Mock()
    github = Mock()
    github.get_repo.return_value = repository
    pull_requests = GithubPullRequests(github, "suttacentral/bilara-data")
    pull_request = Mock()

    pull_requests.close(pull_request)

    pull_request.edit.assert_called_once_with(state="closed")
