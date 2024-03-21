from pathlib import Path
from typing import Literal

import app.services.git.utils as utils
from app.core.config import settings
from app.db.schemas.user import UserBase
from github import Github
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest
from pygit2 import (
    GIT_CHECKOUT_FORCE,
    GIT_DELTA_DELETED,
    GIT_MERGE_ANALYSIS_FASTFORWARD,
    GIT_MERGE_ANALYSIS_NORMAL,
    GIT_MERGE_ANALYSIS_UP_TO_DATE,
    GIT_STATUS_INDEX_DELETED,
    GIT_STATUS_INDEX_MODIFIED,
    GIT_STATUS_INDEX_NEW,
    GIT_STATUS_WT_DELETED,
    GIT_STATUS_WT_MODIFIED,
    GIT_STATUS_WT_NEW,
    Commit,
    GitError,
    Oid,
    RemoteCallbacks,
    Repository,
    Signature,
    UserPass,
)


class GitManager:
    _protected_branches = ("published", "unpublished")
    _git_status = (
        GIT_STATUS_INDEX_NEW,
        GIT_STATUS_INDEX_MODIFIED,
        GIT_STATUS_INDEX_DELETED,
        GIT_STATUS_WT_MODIFIED,
        GIT_STATUS_WT_NEW,
        GIT_STATUS_WT_DELETED,
    )

    def __init__(self, published: Path, unpublished: Path, user: UserBase) -> None:
        self.user = user
        self.published: Repository = Repository(published)
        self.unpublished: Repository = Repository(unpublished)
        self.author: Signature = Signature(name=user.username, email=user.email)
        self.committer: Signature = Signature(name=settings.GITHUB_USERNAME, email=settings.GITHUB_EMAIL)
        self.github: Github = Github(settings.GITHUB_TOKEN)
        self.repo_owner: str = settings.GITHUB_REPO.split("/")[0]

    def pull(
        self, branch: Repository = "published", force: bool = False, remote_name: str = "origin"
    ) -> list[Path] | None:
        branch.state_cleanup()
        if not branch:
            raise GitError(f"Branch {branch} not found")
        branch_name = branch.head.shorthand
        for remote in branch.remotes:
            if remote.name == remote_name:
                remote.fetch()
                remote_hash_id = branch.lookup_reference(f"refs/remotes/{remote_name}/{branch_name}").target
                modified_files = self.get_filenames_from_diff(
                    str(branch.revparse_single("HEAD").id), remote_hash_id, branch
                )
                if force:
                    branch.checkout_tree(branch.get(remote_hash_id), strategy=GIT_CHECKOUT_FORCE)
                    branch.head.set_target(remote_hash_id)
                    branch.state_cleanup()
                    return modified_files
                merge_result, _ = branch.merge_analysis(remote_hash_id)
                if merge_result & GIT_MERGE_ANALYSIS_UP_TO_DATE:
                    branch.state_cleanup()
                    return modified_files
                elif merge_result & GIT_MERGE_ANALYSIS_FASTFORWARD:
                    try:
                        branch.checkout_tree(branch.get(remote_hash_id))
                        head_ref = branch.lookup_reference(f"refs/heads/{branch_name}")
                        head_ref.set_target(remote_hash_id)
                    except KeyError:
                        branch.create_branch(branch_name, branch.get(remote_hash_id))
                    branch.head.set_target(remote_hash_id)
                    branch.state_cleanup()
                    return modified_files
                elif merge_result & GIT_MERGE_ANALYSIS_NORMAL:
                    branch.merge(remote_hash_id, favor="ours")
                    if branch.index.conflicts:
                        conflicts = [conflict for conflict in branch.index.conflicts]
                        branch.state_cleanup()
                        raise GitError(
                            f"'origin/{branch_name}' has local conflict and should be resolved first."
                            f" Use force=True to ignore this error and override all local changes with remote."
                            f" Conflicts in {conflicts}"
                        )
                    tree = branch.index.write_tree()
                    commit_message = f"Merged origin/{branch_name} into {branch.head.shorthand}"
                    branch.create_commit(
                        "HEAD", self.author, self.committer, commit_message, tree, [branch.head.target, remote_hash_id]
                    )
                    branch.state_cleanup()
                    return modified_files
                else:
                    branch.state_cleanup()
                    raise GitError(f"Unexpected merge behaviour")

    def checkout(self, name: str = "published", force: bool = False) -> None:
        self.published.remotes["origin"].fetch(prune=True)
        if not self.published.branches.get(name):
            self.create_local_branch(name)
        ref = self.published.lookup_reference(f"refs/heads/{name}")
        if force:
            self.published.checkout_tree(ref.peel(Commit), strategy=GIT_CHECKOUT_FORCE)
            self.published.head.set_target(ref.target)
        self.published.checkout(ref)

    def copy_files(self, file_paths: list[Path] | None = None) -> list[Path]:
        paths: list[Path] = file_paths or []
        changed_files = [path for path in paths if self.has_changes("unpublished", path)]
        for path in changed_files:
            file_content: bytes | None = GitManager.read_file(self.unpublished, path)
            GitManager.write_file(Path(self.published.workdir) / path, file_content)
        if not GitManager.add(self.published, changed_files):
            return []
        return changed_files

    def create_local_branch(self, name: str) -> bool:
        remote_branch_ref = f"refs/remotes/origin/{name}"
        if f"refs/heads/{name}" in self.published.references:
            return False
        if remote_branch_ref in self.published.references:
            self.published.create_branch(name, self.published.lookup_reference(remote_branch_ref).peel(Commit))
        else:
            self.published.create_branch(name, self.published.revparse_single("HEAD").peel(Commit))
        return True

    def delete_local_branch(self, name: str) -> None:
        self.published.branches.delete(name) if name in self.published.branches else None

    def delete_remote_branch(self, name: str) -> None:
        self.published.remotes["origin"].push(
            [f":refs/heads/{name}"],
            callbacks=RemoteCallbacks(UserPass(settings.GITHUB_USERNAME, settings.GITHUB_TOKEN)),
        )

    def open_pr(self, title, body, head, base="published") -> None:
        repo = self.github.get_repo(settings.GITHUB_REPO)
        if self.is_pr_open(head):
            return
        repo.create_pull(title=title, body=body, base=base, head=head)

    def get_prs(self, head: str, state="open") -> PaginatedList[PullRequest]:
        return self.github.get_repo(settings.GITHUB_REPO).get_pulls(
            state=state, head=f"{self.repo_owner}:{head}", base="published"
        )

    def get_pr(self, head: str, state="open") -> PullRequest | None:
        if (prs := self.get_prs(head, state)) and prs.totalCount > 0:
            return prs[0]

    def is_pr_open(self, head: str) -> bool:
        if prs := self.get_prs(head):
            return prs.totalCount > 0
        return False

    def handle_single_file(self, path: Path, branch, message, pr_title: str = None, pr_body: str = None):
        if not self.has_changes(branch, path):
            return
        if (pr := self.get_pr(branch)) and GitManager.is_file_in_pr(pr, path):
            self._process_branch_changes(pr.head.ref, [path], message)
            self._cleanup(branch)
            return
        self._process_branch_changes(branch, [path], message)
        self.open_pr(title=pr_title, body=pr_body, head=f"{self.repo_owner}:{branch}")

    def handle_multiple_files(self, paths: list[Path], branch, message, pr_title: str = None, pr_body: str = None):
        project_pr = self.get_pr(branch)
        paths_heads = utils.get_file_heads(paths)
        file_prs = [self.get_pr(head) for head in paths_heads.values() if self.is_pr_open(head)]
        for pr in file_prs:
            GitManager.close_pr(pr)
            self.delete_remote_branch(pr.head.ref)
        changed_files = [path for path in paths if self.has_changes(branch, path)]
        files_in_pr = []
        if project_pr:
            files_in_pr = [path for path in changed_files if GitManager.is_file_in_pr(project_pr, path)]
            if files_in_pr:
                self._process_branch_changes(project_pr.head.ref, files_in_pr, message)
        project_files = list(set(changed_files) - set(files_in_pr))
        self._process_branch_changes(branch, project_files, message)
        if not project_pr:
            self.open_pr(title=pr_title, body=pr_body, head=f"{self.repo_owner}:{branch}")

    def has_changes(self, branch_name: str, path: Path) -> bool:
        unpublished_commit: bytes = GitManager.get_latest_commit(self.unpublished, path)
        published_commit: bytes = GitManager.get_latest_commit(self.published, path, branch_name)
        return unpublished_commit != published_commit

    def process_files(self, branch, message, pr_title, pr_body, file_paths: list[Path] | None = None) -> str:
        paths: list[Path] = file_paths or []
        if not paths:
            return ""
        if len(paths) == 1:
            self.handle_single_file(paths[0], branch, message, pr_title, pr_body)
        else:
            self.handle_multiple_files(paths, branch, message, pr_title, pr_body)
        url = self.get_pr(branch).html_url
        self._cleanup(branch)
        return url

    def _cleanup(self, branch: str) -> bool:
        self.checkout(force=True)
        if not self._is_branch_protected(branch):
            self.delete_local_branch(branch)
            return True
        return False

    def _process_branch_changes(self, branch, paths: list[Path], message: str) -> None:
        if not paths:
            return
        self.checkout(branch)
        changed_files = self.copy_files(paths)
        if changed_files and GitManager.commit(self.published, self.author, self.committer, message, changed_files):
            GitManager.push(self.published, branch=branch)

    def _is_branch_protected(self, name: str) -> bool:
        return name in self._protected_branches

    def get_branch(self, name: str) -> Repository:
        return getattr(self, name) if name in self._protected_branches else None

    @staticmethod
    def is_branch_protected(name: str) -> bool:
        return name in GitManager._protected_branches

    @staticmethod
    def add(repo: Repository, file_paths: list[Path] | None = None) -> bool:
        paths: list[Path] = file_paths or []
        if not paths:
            return False
        for path in paths:
            repo.index.add(path)
        repo.index.write()
        return True

    @staticmethod
    def get_filenames_from_diff(commit_id_1: str, commit_id_2: str, branch: Repository) -> list[Path]:
        diff = branch.diff(commit_id_1, commit_id_2)
        if diff.stats.files_changed == 0:
            return []
        return [
            Path(branch.path).parent / Path(patch.delta.new_file.path)
            if patch.delta.status != GIT_DELTA_DELETED
            else Path(branch.path).parent / patch.delta.old_file.path
            for patch in diff
        ]

    @staticmethod
    def separate_existing_files(paths: list[Path]) -> tuple[list[Path], list[Path]]:
        if not paths:
            return [], []

        existing_files = []
        non_existing_files = []
        for path in paths:
            if path.exists():
                existing_files.append(path)
            else:
                non_existing_files.append(path)
        return existing_files, non_existing_files

    @staticmethod
    def remove(repo: Repository, file_paths: list[Path] | None = None) -> bool:
        paths: list[Path] = file_paths or []
        if not paths:
            return False
        for path in paths:
            repo.index.remove(path)
        repo.index.write()
        return True

    @staticmethod
    def read_file(repo: Repository, file_path: Path, branch="unpublished") -> bytes | None:
        branch = repo.branches.get(branch)
        if not branch:
            return None
        try:
            data = branch.peel().tree[file_path].data
        except KeyError:
            return None
        return data

    @staticmethod
    def write_file(dest_path: Path, data: bytes) -> None:
        if not data:
            return None
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)

    @staticmethod
    def commit(
        repo: Repository, author: Signature, committer: Signature, message: str, paths: list[Path] = None
    ) -> Oid | Literal[False]:
        if not GitManager.has_status_changed(repo, paths):
            return False
        return repo.create_commit("HEAD", author, committer, message, repo.index.write_tree(), [repo.head.target])

    @staticmethod
    def push(repo, remote_name="origin", branch="unpublished"):
        remote = repo.remotes[remote_name]
        remote.push(
            ["+refs/heads/%s:refs/heads/%s" % (branch, branch)],
            callbacks=RemoteCallbacks(UserPass(settings.GITHUB_USERNAME, settings.GITHUB_TOKEN)),
        )

    @staticmethod
    def close_pr(pr: PullRequest) -> None:
        pr.edit(state="closed")

    @staticmethod
    def get_latest_commit(repo: Repository, path: Path, branch_name: str = "unpublished") -> bytes | None:
        branch = repo.branches.get(branch_name)
        if not branch:
            return None
        last_commit = branch.peel()
        try:
            data = last_commit.tree[path].data
        except KeyError:
            return None
        return data

    @staticmethod
    def is_file_in_pr(pr: PullRequest, file_path: Path) -> bool:
        if pr.state == "closed":
            return False
        return any(file_path == Path(file.filename) for file in pr.get_files())

    @staticmethod
    def has_status_changed(repo: Repository, paths: list[Path] = None) -> bool:
        if paths:
            for path in paths:
                try:
                    if repo.status_file(str(path)) in GitManager._git_status:
                        return True
                except KeyError:
                    return False
        return False
