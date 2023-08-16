from pathlib import Path

import pygit2
from app.core.config import settings
from github import Github
from pygit2 import Signature


class Git:
    published_repo = pygit2.Repository(Path(str(settings.WORK_DIR).replace("unpublished", "published")))
    unpublished_repo = pygit2.Repository(settings.WORK_DIR)
    committer = Signature(name=settings.GITHUB_USERNAME, email=settings.GITHUB_EMAIL)
    github = Github(settings.GITHUB_TOKEN)

    @staticmethod
    def add(repo, file_path: Path):
        """Adds a file to the repository."""
        repo.index.add(file_path.relative_to(repo.workdir))
        repo.index.write()

    @staticmethod
    def commit(repo, message, author):
        """Commits the added files to the repository."""
        tree = repo.index.write_tree()
        repo.create_commit("HEAD", author, Git.committer, message, tree, [repo.head.peel().hex])

    @staticmethod
    def create_and_checkout_branch(repo, branch_name):
        """Creates a new branch and checks it out."""
        if branch_name not in repo.branches:
            Git.create_branch(repo, branch_name)
        Git.checkout_branch(repo, branch_name)

    @staticmethod
    def create_branch(repo, branch_name):
        """Creates a new branch."""
        repo.create_branch(branch_name, repo.revparse_single("HEAD").peel(pygit2.Commit))

    @staticmethod
    def checkout_branch(repo, branch_name):
        """Checks out a branch."""
        repo.checkout(repo.lookup_reference("refs/heads/" + branch_name))

    @staticmethod
    def read_file(repo, branch_name, file_path):
        """Reads a file from a specific branch."""
        branch = repo.branches[branch_name]
        blob = branch.peel().tree[str(file_path).removeprefix("/app/checkouts/unpublished/")].data
        return blob

    @staticmethod
    def write_file(repo, file_path, data):
        """Writes data to a file in the current branch."""
        with open(Path(repo.workdir) / file_path, "wb") as f:
            f.write(data)

    @staticmethod
    def copy_files_to_branch(source_branch, target_branch, file_paths, message):
        """Copies the specified files from the source branch to the target branch."""
        Git.create_and_checkout_branch(Git.published_repo, target_branch)
        Git.fetch(Git.published_repo, target_branch)
        # if f"origin/{target_branch}" in Git.published_repo.branches:
        #     target_remote_id = Git.published_repo.branches[f"origin/{target_branch}"].target.hex
        #     Git.published_repo.merge(target_remote_id, favor="ours")

        for file_path in file_paths:
            published_file_path = file_path.replace("unpublished", "published")
            data = Git.read_file(Git.unpublished_repo, source_branch, file_path)
            Git.write_file(Git.published_repo, published_file_path, data)
            Git.add(Git.published_repo, Path(published_file_path))

        Git.commit(Git.published_repo, message, Git.committer)
        Git.push(repo=Git.published_repo, branch=target_branch)

        Git.checkout_branch(Git.published_repo, "published")
        Git.delete_local_branch(Git.published_repo, target_branch)

    @staticmethod
    def delete_local_branch(repo, branch_name):
        """Deletes a branch."""
        branch = repo.branches.get(branch_name)
        if branch is not None:
            branch.delete()
        return True

    @staticmethod
    def push(repo, remote_name="origin", branch="unpublished"):
        """Pushes changes to a remote repository."""
        remote = repo.remotes[remote_name]
        remote.push(
            ["+refs/heads/%s:refs/heads/%s" % (branch, branch)],
            callbacks=pygit2.RemoteCallbacks(pygit2.UserPass(settings.GITHUB_USERNAME, settings.GITHUB_TOKEN)),
        )

    @staticmethod
    def fetch(repo, branch_name, remote_name="origin"):
        """Fetches the specified branch from a remote repository. If the branch does not exist on the remote, it creates a new local branch."""
        remote = repo.remotes[remote_name]
        try:
            remote.fetch(
                refspecs=[f"refs/heads/{branch_name}:refs/remotes/{remote_name}/{branch_name}"],
                callbacks=pygit2.RemoteCallbacks(pygit2.UserPass(settings.GITHUB_USERNAME, settings.GITHUB_TOKEN)),
            )
        except KeyError:
            if branch_name not in repo.branches:
                repo.create_branch(repo, branch_name)

    @staticmethod
    def create_pull_request(username, base, head, title, body):
        """Creates a pull request."""
        repo = Git.github.get_repo(settings.GITHUB_REPO)
        if Git.is_pr_open(username, base, head):
            return
        repo.create_pull(title=title, body=body, base=base, head=head)

    @staticmethod
    def is_pr_open(username, base, head):
        repo = Git.github.get_repo(settings.GITHUB_REPO)
        if repo.get_pulls(state="open", head=f"{username}:{head}", base=base).totalCount > 0:
            return True
        return False

    @staticmethod
    def close_pr(username, base, head):
        repo = Git.github.get_repo(settings.GITHUB_REPO)
        for pr in repo.get_pulls(state="open", head=f"{username}:{head}", base=base):
            pr.edit(state="closed")

    @staticmethod
    def get_pr(username, base, head):
        repo = Git.github.get_repo(settings.GITHUB_REPO)
        for pr in repo.get_pulls(state="open", head=f"{username}:{head}", base=base):
            return pr

    @staticmethod
    def get_pr_files(pr):
        return pr.get_files()

    @staticmethod
    def delete_remote_branch(repo, branch_name):
        """Deletes a remote branch."""
        repo.remotes["origin"].push(
            [f":refs/heads/{branch_name}"],
            callbacks=pygit2.RemoteCallbacks(pygit2.UserPass(settings.GITHUB_USERNAME, settings.GITHUB_TOKEN)),
        )

    @staticmethod
    def get_diff_between_remote_branch_and_unpublished(remote, file_path):
        """Returns the diff between the remote branch and the unpublished branch."""
        remote_branch = Git.published_repo.branches[f"origin/{remote}"]
        remote_blob = remote_branch.peel().tree[file_path].id
        local_blob = Git.unpublished_repo.head.peel().tree[file_path].id
        patch = Git.unpublished_repo.diff(local_blob, remote_blob)
        if not patch.data:
            return False
        return patch


# DEFAULT BEHAVIOR:
# copy files and push to remote, open pr, delete local branch
#
# IF MULTIPLE FILES:
# check how many of the files have individual PRs open,
# check how many files have changes, if only one file has changed push changes to its PR
# if multiple files have changed, close all individual PRs and open a new PR with all the files
# if project PR exists, push the changes to that PR
#
# IF ONE FILE:
# check if file has individual PR open, if so push changes to that PR
# if file has no PR open, open it
# if project PR exists, push the changes to that PR if the file is in the PR
# if project PR exists, open a new PR with the file if the file is not in the PR
