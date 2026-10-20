"""Durable dispatch of saved publication metadata through the existing Git queue."""
import fcntl
import logging
import time

from app.services.publications.errors import PublicationError
from app.services.publications.store import PUBLICATION_FILES, PublicationStore
from app.services.sync_dispatch import DELIVERY_LEASE, dispatch_pending as dispatch_sync

logger = logging.getLogger(__name__)


def public_status(state, user):
    if state is None:
        return {"status": "idle", "can_retry": False}
    can_retry = user.role in ("administrator", "superuser") or state["user"]["github_id"] == user.github_id
    return {
        "generation": state["generation"], "status": state["status"],
        "task_id": state["task_id"], "error": state["error"],
        "can_retry": state["status"] == "failed" and can_retry,
    }


def status(work, user):
    store = PublicationStore(work)
    with store.locked():
        return public_status(store.read_sync(), user)


def retry(work, user):
    store = PublicationStore(work)
    with store.locked():
        state = store.read_sync()
        if not public_status(state, user)["can_retry"]:
            raise PublicationError(409, "No failed publication sync is available to retry.")
        state.update(status="pending", task_id=None, dispatch_after=0, error="")
        store.write_sync(state)
        return public_status(state, user)


def update_task_state(work, generation, task_id, **changes):
    store = PublicationStore(work)
    with store.locked():
        state = store.read_sync()
        # A completion or retry for an older save must never clear newer work.
        if (state and state["generation"] == generation and state["task_id"] == task_id
                and state["status"] != "synced"):
            state.update(changes)
            store.write_sync(state)


def dispatch_pending(work):
    """Reserve under the file lock; contact the broker only after releasing it."""
    from app.tasks import sync_publications

    dispatch_sync(PublicationStore(work), sync_publications, update_task_state)


def dispatch_safely(work):
    # Saving already succeeded. Background dispatch failures must not turn the
    # response into a save error; the durable outbox will be checked again.
    try:
        dispatch_pending(work)
    except Exception:
        logger.exception("Unable to dispatch pending publication metadata")


def execute_sync(work, generation, task_id):
    from app.tasks import commit

    store = PublicationStore(work)
    store.directory.mkdir(parents=True, exist_ok=True)
    # Delivery may be repeated after a process crash. Serialize the entire Git
    # operation without holding the metadata write lock during network I/O.
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
                user = state["user"]
            if not commit.run(user, list(PUBLICATION_FILES), "Update publication metadata", safe_push=True):
                raise ValueError("Publication metadata could not be staged for sync.")
            update_task_state(work, generation, task_id, status="synced", error="")
            return True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
