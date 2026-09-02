from pathlib import Path
from unittest.mock import ANY, Mock

import pytest
from pygit2 import GitError, Signature, init_repository

from app.services.git.manager import GitManager
from app.services.git.publication import build_publication_plan


def test_3000_file_publication_uses_one_snapshot_and_returns_created_pull_request_url():
    paths = [
        Path(f"translations/en/test/sutta/an/an1/file-{index}.json")
        for index in range(3000)
    ]
    pull_requests = Mock()
    pull_requests.list_open.return_value = {}
    pull_requests.create.return_value = Mock(
        html_url="https://github.com/example/pull/1"
    )
    manager = object.__new__(GitManager)
    manager.pull_requests = pull_requests
    manager.repo_owner = "suttacentral"
    manager.user = Mock(username="test")
    manager._process_branch_changes = Mock()
    manager._cleanup = Mock()

    result = manager.publish_files(paths)

    assert result == "https://github.com/example/pull/1"
    pull_requests.list_open.assert_called_once_with()
    manager._process_branch_changes.assert_called_once_with(
        "translations_en_test_sutta_an",
        paths,
        "Publishing translations for translations/en/test/sutta/an",
    )
    pull_requests.create.assert_called_once_with(
        title="New translations for translations/en/test/sutta/an",
        body=ANY,
        head="suttacentral:translations_en_test_sutta_an",
    )


def test_unchanged_single_file_does_not_create_pull_request():
    path = Path("translations/en/test/sutta/an/an1/an1.1.json")
    pull_requests = Mock()
    pull_requests.list_open.return_value = {}
    manager = object.__new__(GitManager)
    manager.pull_requests = pull_requests
    manager.repo_owner = "suttacentral"
    manager.user = Mock(username="test")
    manager._process_branch_changes = Mock(return_value=False)
    manager._cleanup = Mock()

    result = manager.publish_files([path])

    assert result == ""
    pull_requests.create.assert_not_called()


def test_multiple_files_consolidate_file_pull_requests_into_project_branch():
    paths = [
        Path("translations/en/test/sutta/an/an1/an1.1.json"),
        Path("translations/en/test/sutta/an/an1/an1.2.json"),
    ]
    first_file_branch = "_".join(str(paths[0]).split("/")).removesuffix(".json")
    second_file_branch = "_".join(str(paths[1]).split("/")).removesuffix(".json")
    first_file_pr = Mock()
    second_file_pr = Mock()

    plan = build_publication_plan(
        paths,
        {
            first_file_branch: first_file_pr,
            second_file_branch: second_file_pr,
        },
    )

    assert plan.target_branch == "translations_en_test_sutta_an"
    assert plan.target_pull_request is None
    assert plan.pull_requests_to_close == (first_file_pr, second_file_pr)


def test_unchanged_multiple_files_do_not_close_existing_file_pull_requests():
    paths = [
        Path("translations/en/test/sutta/an/an1/an1.1.json"),
        Path("translations/en/test/sutta/an/an1/an1.2.json"),
    ]
    file_branch = "_".join(str(paths[0]).split("/")).removesuffix(".json")
    pull_requests = Mock()
    pull_requests.list_open.return_value = {file_branch: Mock()}
    manager = object.__new__(GitManager)
    manager.pull_requests = pull_requests
    manager.repo_owner = "suttacentral"
    manager.user = Mock(username="test")
    manager._process_branch_changes = Mock(return_value=False)
    manager.delete_remote_branch = Mock()
    manager._cleanup = Mock()

    result = manager.publish_files(paths)

    assert result == ""
    pull_requests.close.assert_not_called()
    manager.delete_remote_branch.assert_not_called()
    pull_requests.create.assert_not_called()


def test_single_file_already_in_project_pull_request_updates_project_branch():
    path = Path("translations/en/test/sutta/an/an1/an1.1.json")
    project_pr = Mock()

    plan = build_publication_plan(
        [path],
        {"translations_en_test_sutta_an": project_pr},
        project_pull_request_paths={path},
    )

    assert plan.target_branch == "translations_en_test_sutta_an"
    assert plan.target_pull_request is project_pr
    assert plan.pull_requests_to_close == ()


def test_project_pull_request_with_missing_remote_head_fails_clearly():
    path = Path("translations/en/test/sutta/an/an1/an1.1.json")
    project_branch = "translations_en_test_sutta_an"
    project_pr = Mock()
    project_pr.base.ref = "published"
    project_pr.head.ref = project_branch
    pull_requests = Mock()
    pull_requests.list_open.return_value = {project_branch: project_pr}
    published = Mock()
    published.remotes = {"origin": Mock()}
    base_ref = Mock()
    base_ref.peel.return_value.id = "base-commit"

    def lookup_reference(name):
        if name == "refs/remotes/origin/published":
            return base_ref
        raise KeyError(name)

    published.lookup_reference.side_effect = lookup_reference
    manager = object.__new__(GitManager)
    manager.pull_requests = pull_requests
    manager.published = published

    with pytest.raises(
        GitError,
        match=f"Remote branch origin/{project_branch} is unavailable after fetch",
    ):
        manager.plan_publication([path])


def test_3001_files_update_existing_project_pull_request_without_listing_its_files():
    paths = [
        Path(f"translations/en/test/sutta/an/an1/file-{index}.json")
        for index in range(3001)
    ]
    project_pr = Mock(html_url="https://github.com/example/pull/1")
    project_pr.head.ref = "translations_en_test_sutta_an"
    pull_requests = Mock()
    pull_requests.list_open.return_value = {
        "translations_en_test_sutta_an": project_pr,
    }
    manager = object.__new__(GitManager)
    manager.pull_requests = pull_requests
    manager.repo_owner = "suttacentral"
    manager.user = Mock(username="test")
    manager._process_branch_changes = Mock()
    manager._cleanup = Mock()

    result = manager.publish_files(paths)

    assert result == "https://github.com/example/pull/1"
    project_pr.get_files.assert_not_called()
    pull_requests.create.assert_not_called()


def test_pull_request_file_membership_comes_from_local_git_diff(tmp_path):
    repo_path = tmp_path / "publication-diff"
    repo_path.mkdir()
    repo = init_repository(str(repo_path))
    signature = Signature("Test", "test@example.com")
    path = Path("translations/en/test/sutta/an/an1/an1.1.json")
    file_path = Path(repo.workdir) / path
    file_path.parent.mkdir(parents=True)
    file_path.write_text('{"segment": "first"}')
    repo.index.add(str(path))
    base_tree = repo.index.write_tree()
    base_commit = repo.create_commit(
        "HEAD", signature, signature, "base", base_tree, []
    )

    file_path.write_text('{"segment": "updated"}')
    repo.index.add(str(path))
    head_tree = repo.index.write_tree()
    head_commit = repo.create_commit(
        "HEAD", signature, signature, "head", head_tree, [base_commit]
    )

    changed_paths = GitManager.get_changed_paths(
        repo, str(base_commit), str(head_commit)
    )

    assert changed_paths == {path}
