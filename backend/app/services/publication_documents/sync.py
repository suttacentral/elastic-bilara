"""Recoverable document sync and publication, serialized with checkout writes."""
import fcntl
import logging
from pathlib import Path
import re
import time

from app.services.publication_documents.store import DocumentStore, operations_root, read_html, recover_all, revision
from app.services.publications.errors import PublicationError
from app.services.sync_dispatch import DELIVERY_LEASE, dispatch_pending

logger = logging.getLogger(__name__)


def active_job(job, generation, task_id):
    return (job and job["generation"] == generation and job["task_id"] == task_id
            and job["status"] not in ("synced", "failed"))


def update_task_state(work, generation, task_id, number, operation, **changes):
    store = DocumentStore(work, number, operation)
    with store.locked():
        job = store.read_sync()
        if job and job["generation"] == generation and job["task_id"] == task_id and job["status"] != "synced":
            job.update(changes)
            store.write_sync(job)


def dispatch(work, number):
    from app.tasks import process_publication_documents

    for operation in ("sync", "publish"):
        store = DocumentStore(work, number, operation)
        # Celery prepends the shared dispatcher's generation to these arguments.
        task = process_publication_documents.s(number, operation)
        def update(work, generation, task_id, **changes):
            update_task_state(work, generation, task_id, number, operation, **changes)
        dispatch_pending(store, task, update)


def dispatch_safely(work, number=None):
    numbers = [number] if number else [p.name for p in operations_root(work).glob("scpub*")
                                      if p.is_dir() and re.fullmatch(r"scpub[1-9]\d*", p.name)]
    for current in numbers:
        try:
            dispatch(work, current)
        except Exception:
            logger.exception("Unable to dispatch publication documents for %s", current)


def execute(work, published, generation, task_id, number, operation):
    from app.services.git.manager import GitManager
    from app.services.publication_documents.git import blob_content, publish_documents
    from app.services.publication_documents.service import DocumentService
    from app.services.publication_documents.requests import submission
    from app.services.users.utils import get_user
    from app.tasks import commit_local, sync_committed

    store = DocumentStore(work, number, operation)
    store.directory.mkdir(parents=True, exist_ok=True)
    with (store.directory / "execution.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            with store.locked():
                job = store.read_sync()
                if not active_job(job, generation, task_id):
                    return False
                job.update(status="syncing", error="", dispatch_after=time.time() + DELIVERY_LEASE)
                store.write_sync(job)
            user = get_user(job["user"]["github_id"])
            service = DocumentService(work, published, user)
            manager = GitManager(published, work, user)
            # Recover, validate and commit as one local operation. A writer may
            # save a new draft as soon as this block ends, including during push.
            with store.locked():
                recover_all(work)
                job = store.read_sync()
                if not active_job(job, generation, task_id):
                    return False
                paths = []
                contents = {}
                for uid, target in job["documents"].items():
                    doc, path = service._document(number, uid)
                    content = read_html(path)
                    if doc["path"] != target["path"] or revision(content) != target["revision"]:
                        raise PublicationError(409, f"{path.name} changed after this operation was requested. Review and submit it again.")
                    if operation == "publish" and not service._validation(doc, content)["valid"]:
                        raise PublicationError(422, f"Resolve validation errors in {path.name} before publishing.")
                    paths.append(Path(target["path"]))
                    contents[uid] = content
                if not commit_local(manager, paths, f"Edit publication documents for {number}"):
                    raise PublicationError(409, "The selected document changes could not be committed.")
            synced_commit = sync_committed(manager, safe_push=True)
            result = {}
            if operation == "publish":
                with store.locked():
                    if not active_job(store.read_sync(), generation, task_id):
                        return False
                    for uid, target in job["documents"].items():
                        service._document(number, uid)
                        if revision(blob_content(synced_commit, target["path"])) != target["revision"]:
                            raise PublicationError(409, "Remote changes were merged into the draft. Review the latest content before publishing.")
                result = publish_documents(manager, number, job, contents, job.get("previous"))
            with store.locked():
                state = store.read()
                previous = submission(state)
                if operation == "publish":
                    request_number = result["request_number"]
                    if not previous or previous["number"] != request_number:
                        state["submitted"] = {}
                    if request_number is not None:
                        state["submitted"].update(job["documents"])
                        if not previous or previous["number"] != request_number:
                            state["submission"] = {"number": request_number, "url": result["url"],
                                                   "state": "open", "checked_at": 0}
                        else:
                            state["submission"] = previous
                        result["request_state"] = state["submission"]["state"]
                    else:
                        state.pop("submission", None)
                # A new save/delivery may have replaced this job during network
                # I/O. Record a submitted PR, but never clear the newer intent.
                if active_job(state[operation], generation, task_id):
                    state[operation].update(status="synced", error="", **result)
                store.write(state)
                return True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
