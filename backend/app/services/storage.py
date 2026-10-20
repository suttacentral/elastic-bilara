"""Durable JSON replacement shared by recoverable file operations."""
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path


class StorageError(OSError):
    """File or lock I/O failed; background Git tasks may retry it."""


@contextmanager
def storage_errors():
    """Translate only I/O owned by this module, never a lock caller's body."""
    try:
        yield
    except OSError as exc:
        raise StorageError(*exc.args) from exc


def write_json(path: Path, value):
    with storage_errors():
        temporary = None
        try:
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                os.fchmod(handle.fileno(), mode)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
