"""Reentrant checkout exclusion; callers own recovery of the files they access."""
import fcntl
from contextlib import contextmanager
from pathlib import Path
from threading import local

from app.services.storage import storage_errors

_held = local()


@contextmanager
def checkout_lock(work):
    work = Path(work).resolve()
    # Keep the existing lock location for publication/Git compatibility.
    directory = work.parent / ".publication-operations" / work.name
    held = getattr(_held, "paths", set())
    if work in held:
        yield
        return
    with storage_errors():
        directory.mkdir(parents=True, exist_ok=True)
        handle = (directory / "lock").open("a+")
    try:
        with storage_errors():
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            _held.paths = held | {work}
            yield
        finally:
            _held.paths = held
            with storage_errors():
                fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        handle.close()
