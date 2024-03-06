import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.services.projects.utils import write_json_data
from pygit2 import Blob, Oid, Signature
from search.utils import get_json_data


class TestManager:
    @pytest.mark.parametrize("force", [True, False])
    def test_checkout_without_new_remote_branch(self, force, git_manager):
        branch = "test_branch"
        ref = f"refs/heads/{branch}"
        git_manager.checkout(branch, force=force)
        assert git_manager.published.head.name == ref
        assert git_manager.published.lookup_reference(ref)
        assert git_manager.published.branches.get(branch).is_head()

    @pytest.mark.parametrize("force", [True, False])
    def test_checkout_with_remote_branch(self, force, git_manager):
        branch = "remote_test_branch"
        ref_local = f"refs/heads/{branch}"
        ref_remote = f"refs/remotes/origin/{branch}"
        git_manager.published.create_reference(ref_remote, git_manager.published.head.target)

        git_manager.checkout(branch, force=force)
        assert git_manager.published.head.name == ref_local
        assert git_manager.published.branches.get(branch).is_head()

    def test_create_local_branch(self, git_manager):
        branch = "test_branch"
        git_manager.create_local_branch(branch)
        assert git_manager.published.branches.get(branch)

    def test_delete_local_branch_existing_branch(self, git_manager):
        branch = "existing_branch"
        git_manager.create_local_branch(branch)
        assert git_manager.published.branches.get(branch)
        git_manager.delete_local_branch(branch)
        assert not git_manager.published.branches.get(branch)

    def test_delete_local_branch_non_existing_branch(self, git_manager):
        branch = "non_existing_branch"
        assert not git_manager.published.branches.get(branch)
        git_manager.delete_local_branch(branch)
        assert not git_manager.published.branches.get(branch)

    @pytest.mark.parametrize(
        "repo_attr, file_path, branch_name, expected_result, expected_type",
        [
            (
                "published",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                "published",
                None,
                Blob | bytes,
            ),
            ("published", Path("non_existent_file.txt"), "published", None, None),
            (
                "published",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                "non_existent_branch",
                None,
                None,
            ),
            (
                "unpublished",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                "unpublished",
                None,
                Blob | bytes,
            ),
            ("unpublished", Path("non_existent_file.txt"), "unpublished", None, None),
            (
                "unpublished",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                "non_existent_branch",
                None,
                None,
            ),
        ],
    )
    def test_get_latest_commit(
        self,
        repo_attr,
        file_path,
        branch_name,
        expected_result,
        expected_type,
        git_manager,
    ):
        repo = getattr(git_manager, repo_attr)
        dir_map = {"published": git_manager.published.workdir, "unpublished": git_manager.unpublished.workdir}

        result = git_manager.get_latest_commit(repo, file_path, branch_name)
        assert isinstance(result, expected_type) if expected_type else result is expected_result

        if expected_type is Blob:
            with open(dir_map[repo_attr] / file_path, "r") as f:
                expected_content = json.load(f)
            assert result == json.dumps(expected_content, indent=4).encode()

    @pytest.mark.parametrize(
        "repo_attr, author, committer, message, paths, expected_result_type",
        [
            (
                "published",
                Signature("Test", "test@test.com"),
                Signature("Test", "test@test.com"),
                "Test commit with changes",
                [Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json")],
                Oid,
            ),
            (
                "published",
                Signature("Test", "test@test.com"),
                Signature("Test", "test@test.com"),
                "Test commit without changes",
                None,
                bool,
            ),
        ],
    )
    def test_commit(self, repo_attr, author, committer, message, paths, expected_result_type, git_manager):
        repo = getattr(git_manager, repo_attr)

        if paths:
            file_path = Path(git_manager.published.workdir) / paths[0]
            with open(file_path, "r") as f:
                content = json.load(f)

            content["an1.1:1.2"] = "Modified content for testing"

            with open(file_path, "w") as f:
                json.dump(content, f, indent=4)

            repo.index.add(str(paths[0]))

        result = git_manager.commit(repo, author, committer, message, paths)
        assert isinstance(result, expected_result_type)

        if expected_result_type is Oid:
            last_commit = repo[repo.head.target]
            assert last_commit.message == message
            assert last_commit.author == author
            assert last_commit.committer == committer

    @pytest.mark.parametrize(
        "repo_attr, paths, expected_result",
        [
            (
                "published",
                [Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json")],
                True,
            ),
            ("published", [Path("translations/en/test/sutta/an/an1/non_existent_file.json")], False),
            ("published", None, False),
        ],
    )
    def test_has_status_changed(self, repo_attr, paths, expected_result, git_manager):
        repo = getattr(git_manager, repo_attr)

        if paths and expected_result:
            file_path = Path(git_manager.published.workdir) / paths[0]
            with open(file_path, "r") as f:
                content = json.load(f)

            content["an1.1:1.2"] = "Modified content for testing"

            with open(file_path, "w") as f:
                json.dump(content, f, indent=4)

            repo.index.add(str(paths[0]))

        result = git_manager.has_status_changed(repo, paths)
        assert result == expected_result

    @pytest.mark.parametrize(
        "branch, file_path, expected_result",
        [
            (
                "unpublished",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                Blob,
            ),
            ("unpublished", Path("translations/en/test/sutta/an/an1/non_existent_file.json"), None),
            ("non_existent_branch", Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"), None),
        ],
    )
    def test_read_file(self, branch, file_path, expected_result, git_manager):
        result = git_manager.read_file(git_manager.unpublished, file_path, branch)
        if expected_result is Blob:
            assert isinstance(result, Blob | bytes)
        else:
            assert result == expected_result

    @pytest.mark.parametrize(
        "file_paths, expected_result",
        [
            (None, False),
            ([], False),
            (
                [
                    Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                    Path("translations/en/test/sutta/an/an1/new_file.json"),
                ],
                True,
            ),
        ],
    )
    def test_add(self, file_paths, expected_result, git_manager):
        repo = git_manager.unpublished

        if file_paths and "new_file.json" in str(file_paths[-1]):
            new_file_path = (
                Path(repo.workdir) / "translations" / "en" / "test" / "sutta" / "an" / "an1" / "new_file.json"
            )
            with open(new_file_path, "w") as f:
                json.dump({"data": "new data"}, f, indent=4)

        result = git_manager.add(repo, file_paths)

        assert result == expected_result

        if expected_result:
            for file_path in file_paths:
                assert str(file_path) in repo.index

    @pytest.mark.parametrize(
        "file_paths, expected_result",
        [
            (None, False),
            ([], False),
            (
                [
                    Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                    Path("translations/en/test/sutta/an/an1/new_file.json"),
                ],
                True,
            ),
        ],
    )
    def test_remove(self, file_paths, expected_result, git_manager):
        repo = git_manager.unpublished

        if file_paths:
            new_file_path = (
                Path(repo.workdir) / "translations" / "en" / "test" / "sutta" / "an" / "an1" / "new_file.json"
            )
            with open(new_file_path, "w") as f:
                json.dump({"data": "new data"}, f, indent=4)
            git_manager.add(repo, file_paths)
            new_file_path.unlink()

        result = git_manager.remove(repo, file_paths)

        assert result == expected_result

        if expected_result:
            for file_path in file_paths:
                assert str(file_path) not in repo.index

    @pytest.mark.parametrize(
        "branch, expected_output",
        [
            ("test_branch", True),
            ("published", False),
            ("unpublished", False),
        ],
    )
    def test_cleanup(self, branch, expected_output, git_manager):
        git_manager.create_local_branch(branch)
        assert git_manager.published.branches.get(branch)
        assert git_manager._cleanup(branch) == expected_output
        assert not bool(git_manager.published.branches.get(branch)) == expected_output

    @pytest.mark.parametrize(
        "paths, expected_output",
        [
            (None, []),
            ([], []),
            (
                [Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json")],
                [Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json")],
            ),
        ],
    )
    def test_copy_files(self, paths, expected_output, git_manager):
        initial_states_published = (
            {path: git_manager.read_file(git_manager.published, path, "published") for path in paths} if paths else []
        )
        initial_states_unpublished = (
            {path: git_manager.read_file(git_manager.unpublished, path) for path in paths} if paths else []
        )
        git_manager.checkout("test_branch")
        changed_files = git_manager.copy_files(paths)
        assert changed_files == expected_output
        for path in changed_files:
            git_manager.commit(git_manager.published, git_manager.author, git_manager.committer, "Test commit", [path])
        for path in changed_files:
            assert git_manager.read_file(git_manager.published, path, "test_branch") == initial_states_unpublished[path]
            assert git_manager.read_file(git_manager.unpublished, path) != initial_states_published[path]

    @pytest.mark.parametrize(
        "branch, path, changes_made, expected_result",
        [
            (
                "test_branch",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                {"an1.1:0.1": "Modified Content"},
                True,
            ),
            (
                "test_branch",
                Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                {"an1.1:0.1": "Numbered Discourses 1.1–10 "},
                False,
            ),
        ],
    )
    def test_has_changes(self, branch, path, changes_made, expected_result, git_manager):
        git_manager.checkout(branch)
        file_path_published = Path(git_manager.published.workdir) / path
        git_manager.copy_files([path])
        git_manager.commit(git_manager.published, git_manager.author, git_manager.committer, "Test commit", [path])
        assert not git_manager.has_changes(branch, path)

        data = get_json_data(file_path_published)
        data.update(changes_made)
        write_json_data(file_path_published, data)
        git_manager.add(git_manager.published, [path])
        git_manager.commit(git_manager.published, git_manager.author, git_manager.committer, "Test commit", [path])
        assert git_manager.has_changes(branch, path) == expected_result

    @pytest.mark.parametrize(
        "paths, expected_single_call, expected_multiple_calls",
        [
            ([Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json")], True, False),
            (
                [
                    Path("translations/en/test/sutta/an/an1/an1.1-10_translation-en-test.json"),
                    Path("translations/en/test/sutta/an/an1/an1.11-20_translation-en-test.json"),
                ],
                False,
                True,
            ),
            ([], False, False),
            (None, False, False),
        ],
    )
    def test_process_files(self, paths, expected_single_call, expected_multiple_calls, git_manager):
        git_manager.handle_single_file = Mock()
        git_manager.handle_multiple_files = Mock()
        git_manager.get_pr = Mock(return_value=Mock(html_url="test_url"))
        git_manager._cleanup = Mock()
        git_manager.process_files("test_branch", "Test commit", "Test PR title", "Test PR body", paths)
        assert git_manager.handle_single_file.called == expected_single_call
        assert git_manager.handle_multiple_files.called == expected_multiple_calls
