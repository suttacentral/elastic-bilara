import fcntl
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings


def _lock_path(path: Path) -> Path:
    canonical_path = str(path.resolve())
    digest = hashlib.sha256(canonical_path.encode()).hexdigest()
    return settings.WORK_DIR.parent / ".locks" / f"{digest}.lock"


@contextmanager
def project_file_lock(path: Path) -> Iterator[None]:
    lock_path = _lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
