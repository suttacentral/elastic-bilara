"""Shared delivery reservation and periodic checks for durable sync intents."""
import asyncio
import logging
import time
from uuid import uuid4

from kombu.exceptions import OperationalError

logger = logging.getLogger(__name__)
RECONCILE_INTERVAL = 60
DISPATCH_RETRY_DELAY = 15
# Longer than GitTask's longest ordinary retry delay (about 30 minutes).
DELIVERY_LEASE = 3600


def dispatch_pending(store, task, update_state):
    """Reserve under the store lock, then contact the broker after releasing it."""
    with store.locked():
        state = store.read_sync()
        if not state or state['status'] in ('synced', 'failed') or state['dispatch_after'] > time.time():
            return
        task_id = str(uuid4())
        generation = state['generation']
        state.update(status='queued', task_id=task_id, dispatch_after=time.time() + DELIVERY_LEASE)
        store.write_sync(state)
    try:
        task.apply_async(args=[generation], task_id=task_id, retry=False)
    except (OSError, OperationalError) as exc:
        # Each domain retains its own generation and terminal-state rules.
        update_state(store.work, generation, task_id, status='pending', error=str(exc),
                     dispatch_after=time.time() + DISPATCH_RETRY_DELAY)
        logger.warning('Sync task %s remains pending: %s', task.name, exc)


def dispatch_all(work):
    from app.services.publications import sync as publications
    from app.services.tags import sync as tags

    # Each entry point contains its own failures so both domains are checked.
    publications.dispatch_safely(work)
    tags.dispatch_safely(work)


async def dispatch_loop(work):
    while True:
        await asyncio.to_thread(dispatch_all, work)
        await asyncio.sleep(RECONCILE_INTERVAL)
