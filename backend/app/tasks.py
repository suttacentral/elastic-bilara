import elasticsearch.exceptions
from app.celery import celery_app as app
from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.git import utils
from app.services.git.manager import GitManager
from celery import Task
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError
from elasticsearch.exceptions import ConnectionTimeout as ElasticConnectionTimeout
from elasticsearch.exceptions import NotFoundError as ElasticNotFoundError
from elasticsearch.exceptions import RequestError as ElasticRequestError
from github import GithubException
from pygit2 import GitError
from search.search import Search

es = Search()


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


class SyncTask(GitTask):
    auto_retry_for = (
        OSError,
        ConnectionError,
        TimeoutError,
        GithubException,
        ElasticConnectionError,
        ElasticConnectionTimeout,
        ElasticRequestError,
        ElasticNotFoundError,
    )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        manager = kwargs.get("manager")
        branch = kwargs.get("branch")
        if manager and branch:
            manager._cleanup(branch)
        super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(name="commit", base=GitTask, queue="commit_queue")
def commit(user: dict, file_paths: list[str], message: str, add: bool = True) -> bool:
    file_paths = [file_paths] if isinstance(file_paths, str) else file_paths
    paths = [utils.clean_path(path) for path in file_paths if path]
    if not paths:
        return False

    user_data = UserBase(**user)
    manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user_data)
    git_operation = GitManager.add if add else GitManager.remove
    
    if not (
        git_operation(manager.unpublished, paths)
        and GitManager.commit(manager.unpublished, manager.author, manager.committer, message, paths)
    ):
        return False

    changed_files = manager.pull(manager.unpublished)
    GitManager.push(manager.unpublished, "origin", "unpublished")

    existing_paths, not_existing_paths = manager.separate_existing_files(changed_files)
    if existing_paths:
        es.update_indexes(settings.ES_INDEX, settings.ES_SEGMENTS_INDEX, existing_paths)
    if not_existing_paths:
        es.update_indexes(settings.ES_INDEX, settings.ES_SEGMENTS_INDEX, not_existing_paths, delete=True)
    return True


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


@app.task(name="pull", base=GitTask, queue="sync_queue")
def pull(user_data: dict, branch_name: str, force: bool = False, remote_name: str = "origin") -> None:
    manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, UserBase(**user_data))
    branch = manager.get_branch(branch_name)
    changed_files = manager.pull(branch, force=force, remote_name=remote_name)

    existing_paths, not_existing_paths = manager.separate_existing_files(changed_files)
    es.update_indexes(settings.ES_INDEX, settings.ES_SEGMENTS_INDEX, existing_paths)
    if not_existing_paths:
        es.update_indexes(settings.ES_INDEX, settings.ES_SEGMENTS_INDEX, not_existing_paths, delete=True)


@app.task(name="push", base=GitTask, queue="sync_queue")
def push(user_data: dict, branch_name: str, remote_name: str = "origin") -> None:
    manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, UserBase(**user_data))
    branch = manager.get_branch(branch_name)

    manager.push(branch, remote_name, branch_name)
