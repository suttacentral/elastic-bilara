from app.celery import celery_app as app
from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.git import utils
from app.services.git.manager import GitManager
from celery import Task
from github import GithubException
from pygit2 import GitError


class GitTask(Task):
    auto_retry_for = (OSError, ConnectionError, TimeoutError, GitError, GithubException)
    max_retries = 15
    initial_backoff = 0.1098
    backoff_factor = 2

    def __call__(self, *args, **kwargs):
        try:
            return super().__call__(*args, **kwargs)
        except self.auto_retry_for as exc:
            retry_count = self.request.retries
            backoff = self.initial_backoff * (self.backoff_factor**retry_count)  # at most an hour
            self.retry(exc=exc, countdown=backoff, max_retries=self.max_retries)


class PrTask(GitTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        user, file_paths = args
        paths = [utils.clean_path(path) for path in file_paths]
        user_data = UserBase(**user)
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        branch = utils.get_branch_name(manager, paths)
        manager._cleanup(branch)
        super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(name="commit_batch", base=GitTask, queue="commit_queue")
def commit(user: dict, file_paths: list[str], message: str) -> bool:
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    paths = [utils.clean_path(path) for path in file_paths]
    if not all(paths):
        return False
    user_data = UserBase(**user)
    manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
    if GitManager.add(manager.unpublished, paths) and GitManager.commit(
        manager.unpublished, manager.author, manager.committer, message, paths
    ):
        GitManager.push(manager.unpublished, "origin", "unpublished")
        return True
    return False


@app.task(name="pr", base=PrTask, queue="pr_queue")
def pr(user, file_paths) -> str:
    user_data = UserBase(**user)
    paths = [utils.clean_path(path) for path in file_paths]
    if not paths:
        return ""
    manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
    branch = utils.get_branch_name(manager, paths)
    commit_message = utils.get_pr_commit_message(branch)
    pr_title = utils.get_pr_title(branch)
    pr_body = utils.get_pr_body(user_data)
    return manager.process_files(
        message=commit_message, branch=branch, pr_title=pr_title, pr_body=pr_body, file_paths=paths
    )
