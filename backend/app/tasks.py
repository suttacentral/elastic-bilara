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

redis_conn = Redis(host="redis", port=6379, password="test")

lock = Lock(redis_conn, "lock")


class PrTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        user, file_paths = args
        paths = [utils.clean_path(path) for path in file_paths]
        user_data = UserData(**user)
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        branch = utils.get_branch_name(user_data, paths)
        manager._cleanup(branch)
        super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(name="commit", auto_retry_for=(IOError, GitError), retry_kwargs={"max_retries": 5}, retry_backoff=True)
def commit(user: dict, file_path: str):
    with lock:
        path = utils.clean_path(file_path)
        user_data = UserData(**user)
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        message = f"Translations by {user_data.username} to {path}"
        GitManager.add(manager.unpublished, [path])
        GitManager.commit(manager.unpublished, manager.author, manager.committer, message)
        return user


@app.task(name="push", auto_retry_for=(IOError, GitError), retry_kwargs={"max_retries": 10}, retry_backoff=True)
def push(user: dict, remote: str = "origin", branch: str = "unpublished"):
    with lock:
        user_data = UserData(**user)
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        GitManager.push(manager.unpublished, remote, branch)


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
        manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
        branch = utils.get_branch_name(user_data, paths)
        commit_message = utils.get_pr_commit_message(branch)
        pr_title = utils.get_pr_title(branch)
        pr_body = utils.get_pr_body(user_data)
        return manager.process_files(
            message=commit_message, branch=branch, pr_title=pr_title, pr_body=pr_body, file_paths=paths
        )
