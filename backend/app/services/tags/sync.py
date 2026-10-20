"""Durable tag outbox delivered through the existing Git commit queue."""
import fcntl
import logging
import time
from pathlib import Path
from uuid import uuid4

from pygit2 import Signature

from app.services.sync_dispatch import DELIVERY_LEASE, dispatch_pending as dispatch_sync
from app.services.tags.store import TagError, TagStore

logger = logging.getLogger(__name__)


def public_status(state):
    if state is None:
        return {"status": "idle", "can_retry": False}
    return {"generation": state["generation"], "status": state["status"],
            "task_id": state["task_id"], "error": state["error"],
            "files_count": len(state["paths"]), "can_retry": state["status"] == "failed"}


def status(work):
    store = TagStore(work)
    with store.locked():
        return public_status(store.read_sync())


def retry(work):
    store = TagStore(work)
    with store.locked():
        state = store.read_sync()
        if not public_status(state)["can_retry"]:
            raise TagError(409, "No failed tag sync is available to retry.")
        # A fresh generation also invalidates any callbacks from the failed run.
        state.update(generation=str(uuid4()), status="pending", task_id=None, dispatch_after=0, error="")
        store.write_sync(state)
        return public_status(state)


def update_task_state(work, generation, task_id, **changes):
    store = TagStore(work)
    with store.locked():
        state = store.read_sync()
        if (state and state["generation"] == generation and state["task_id"] == task_id
                and state["status"] not in ("synced", "failed")):
            state.update(changes)
            store.write_sync(state)


def dispatch_pending(work):
    from app.tasks import sync_tags

    dispatch_sync(TagStore(work), sync_tags, update_task_state)


def dispatch_safely(work):
    try:
        dispatch_pending(work)
    except Exception:
        logger.exception("Unable to dispatch pending tag changes")


def commit_pending_batch(repo, paths, committer):
    """Commit an overlapping batch with its recorded author and message.

    Caller holds the checkout lock and has recovered tag files. True means
    the batch still needs sync confirmation, even if an earlier attempt already
    committed it. This local step never marks the batch synced.
    """
    from app.services.git.manager import GitManager

    state = TagStore(repo.workdir).read_sync()
    if (not state or state['status'] == 'synced'
            or not {Path(path).as_posix() for path in paths}.intersection(state['paths'])):
        return False
    batch_paths = [Path(path) for path in state['paths']]
    author = Signature(state['user']['username'], state['user']['email'])
    if not GitManager.add(repo, batch_paths):
        raise ValueError('Tag changes could not be staged for sync.')
    GitManager.commit(repo, author, committer, state['message'], batch_paths)
    return True


def execute_sync(work, generation, task_id):
    from app.tasks import commit

    store = TagStore(work)
    store.directory.mkdir(parents=True, exist_ok=True)
    with (store.directory / "sync.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            with store.locked():
                state = store.read_sync()
                if (not state or state["generation"] != generation or state["task_id"] != task_id
                        or state["status"] in ("synced", "failed")):
                    return False
                state.update(status="syncing", error="", dispatch_after=time.time() + DELIVERY_LEASE)
                store.write_sync(state)
            if not commit.run(state["user"], state["paths"], state["message"], safe_push=True):
                raise ValueError("Tag changes could not be staged for sync.")
            update_task_state(work, generation, task_id, status="synced", error="")
            return True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
