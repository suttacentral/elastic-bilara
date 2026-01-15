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


@app.task(name="update_all_translation_progress", queue="commit_queue")
def update_all_translation_progress() -> dict:
    from pathlib import Path
    from datetime import datetime
    from app.db.database import get_sess
    from app.db.models.translation_progress import TranslationProgress
    from search.utils import find_root_path, get_json_data, get_muid, get_prefix

    translation_dir = settings.WORK_DIR / "translation"
    if not translation_dir.exists():
        return {"status": "error", "message": "Translation directory not found"}

    updated_count = 0
    error_count = 0

    with get_sess() as db:
        for file_path in translation_dir.rglob("*.json"):
            try:
                source_path = find_root_path(file_path)
                if not source_path:
                    continue

                translation_data = get_json_data(file_path)
                source_data = get_json_data(source_path)

                total_keys = len(source_data)
                translated_keys = sum(
                    1 for key in source_data
                    if key in translation_data and translation_data[key] and str(translation_data[key]).strip()
                )
                progress = (translated_keys / total_keys * 100) if total_keys > 0 else 0.0

                relative_path = str(file_path.relative_to(settings.WORK_DIR))

                existing = db.query(TranslationProgress).filter(
                    TranslationProgress.file_path == relative_path
                ).first()

                if existing:
                    existing.progress = round(progress, 2)
                    existing.total_keys = total_keys
                    existing.translated_keys = translated_keys
                    existing.updated_at = datetime.utcnow()
                else:
                    new_record = TranslationProgress(
                        file_path=relative_path,
                        prefix=get_prefix(file_path),
                        muid=get_muid(file_path),
                        progress=round(progress, 2),
                        total_keys=total_keys,
                        translated_keys=translated_keys,
                    )
                    db.add(new_record)

                updated_count += 1

            except Exception as e:
                error_count += 1
                print(f"Error processing {file_path}: {e}")

        db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "error_count": error_count,
    }


@app.task(name="update_file_translation_progress", queue="commit_queue")
def update_file_translation_progress(file_path: str) -> dict:
    from pathlib import Path
    from datetime import datetime
    from app.db.database import get_sess
    from app.db.models.translation_progress import TranslationProgress
    from search.utils import find_root_path, get_json_data, get_muid, get_prefix

    path = Path(file_path) if Path(file_path).is_absolute() else settings.WORK_DIR / file_path

    if not path.exists() or not path.suffix == ".json":
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        source_path = find_root_path(path)
        if not source_path:
            return {"status": "error", "message": "Source file not found"}

        translation_data = get_json_data(path)
        source_data = get_json_data(source_path)

        total_keys = len(source_data)
        translated_keys = sum(
            1 for key in source_data
            if key in translation_data and translation_data[key] and str(translation_data[key]).strip()
        )
        progress = (translated_keys / total_keys * 100) if total_keys > 0 else 0.0

        relative_path = str(path.relative_to(settings.WORK_DIR))

        with get_sess() as db:
            existing = db.query(TranslationProgress).filter(
                TranslationProgress.file_path == relative_path
            ).first()

            if existing:
                existing.progress = round(progress, 2)
                existing.total_keys = total_keys
                existing.translated_keys = translated_keys
                existing.updated_at = datetime.utcnow()
            else:
                new_record = TranslationProgress(
                    file_path=relative_path,
                    prefix=get_prefix(path),
                    muid=get_muid(path),
                    progress=round(progress, 2),
                    total_keys=total_keys,
                    translated_keys=translated_keys,
                )
                db.add(new_record)

            db.commit()

        return {
            "status": "success",
            "file_path": relative_path,
            "progress": round(progress, 2),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
