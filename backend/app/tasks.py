from app.celery import celery_app as app
from app.core.config import settings
from app.services.git import utils
from app.services.git.manager import GitManager
from app.services.users.schema import UserData
from celery import Task
from github import GithubException
from pygit2 import GitError
from redis import Redis
from redis.lock import Lock

lock = Lock(
    Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD),
    "lock",
    blocking_timeout=300,
)


class PrTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        user, file_paths = args
        paths = [utils.clean_path(path) for path in file_paths]
        user_data = UserData(**user)
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        branch = utils.get_branch_name(manager, paths)
        manager._cleanup(branch)
        super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(
    name="commit",
    auto_retry_for=(IOError, GitError, GithubException),
    retry_kwargs={"max_retries": 15},
    retry_backoff=True,
)
def commit(user: dict, file_path: str) -> bool:
    with lock:
        path = utils.clean_path(file_path)
        if not path:
            return False
        user_data = UserData(**user)
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        message = f"Translations by {user_data.username} to {path}"
        if GitManager.add(manager.unpublished, [path]) and GitManager.commit(
            manager.unpublished, manager.author, manager.committer, message, [path]
        ):
            GitManager.push(manager.unpublished, "origin", "unpublished")
            return True
        return False


@app.task(
    base=PrTask,
    name="pr",
    auto_retry_for=(IOError, GitError, GithubException),
    retry_kwargs={"max_retries": 15},
    retry_backoff=True,
)
def pr(user, file_paths) -> str:
    with lock:
        user_data = UserData(**user)
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
