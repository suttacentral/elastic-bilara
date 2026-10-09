"""Locked, recoverable writes of both publication files.

A durable redo journal is completed before readers or Git operations proceed.
Replacing two files is not a filesystem-wide atomic operation.
"""
import fcntl
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import local

from app.services.publications.errors import PublicationError, PublicationStorageError

PUBLICATION_FILES = ("_publication-v2.json", "_publication.json")
_held_locks = local()


@contextmanager
def _storage_errors():
    """Translate only I/O owned by this module, never a lock caller's body."""
    try:
        yield
    except OSError as exc:
        raise PublicationStorageError(*exc.args) from exc


def write_json(path: Path, value):
    with _storage_errors():
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


class PublicationStore:
    def __init__(self, work: Path):
        with _storage_errors():
            self.work = Path(work).resolve()
        self.directory = self.work.parent / ".publication-operations" / self.work.name
        self.journal = self.directory / "pending.json"

    @contextmanager
    def locked(self):
        held = getattr(_held_locks, "paths", set())
        if self.directory in held:
            yield self
            return
        with _storage_errors():
            self.directory.mkdir(parents=True, exist_ok=True)
            handle = (self.directory / "lock").open("a+")
        try:
            with _storage_errors():
                fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                _held_locks.paths = held | {self.directory}
                self.recover()
                yield self
            finally:
                _held_locks.paths = held
                with _storage_errors():
                    fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            with _storage_errors():
                handle.close()

    def recover(self):
        with _storage_errors():
            if not self.journal.exists():
                return
            pending = json.loads(self.journal.read_text(encoding="utf-8"))
        if pending is not None:
            self._apply(pending)

    def read_v2(self):
        try:
            with _storage_errors():
                entries = json.loads((self.work / PUBLICATION_FILES[0]).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PublicationError(409, "Publication v2 contains invalid JSON; an administrator must repair it.") from exc
        if not isinstance(entries, list):
            raise PublicationError(409, "Invalid publication v2 structure.")
        numbers = [entry.get("publication_number") for entry in entries if isinstance(entry, dict)]
        if len(numbers) != len(entries) or any(not isinstance(n, str) or not n for n in numbers):
            raise PublicationError(409, "Invalid publication numbers.")
        if len(set(numbers)) != len(numbers):
            raise PublicationError(409, "Duplicate publication numbers must be resolved before editing.")
        return entries

    def read_legacy(self):
        try:
            with _storage_errors():
                path = self.work / PUBLICATION_FILES[1]
                legacy = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except json.JSONDecodeError as exc:
            raise PublicationError(409, "Compatibility output contains invalid JSON; an administrator must repair it before saving.") from exc
        if not isinstance(legacy, dict) or any(
            not isinstance(entry, dict) or entry.get("publication_number") != number
            for number, entry in legacy.items()
        ):
            raise PublicationError(409, "Invalid compatibility output structure.")
        return legacy

    def read(self):
        return self.read_v2(), self.read_legacy()

    def save(self, v2, legacy):
        pending = dict(zip(PUBLICATION_FILES, (v2, legacy)))
        write_json(self.journal, pending)
        self._apply(pending)

    def _apply(self, pending):
        for name in PUBLICATION_FILES:
            write_json(self.work / name, pending[name])
        write_json(self.journal, None)
