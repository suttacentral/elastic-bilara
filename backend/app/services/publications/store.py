"""Locked, recoverable writes of both publication files.

A durable redo journal is completed before readers or Git operations proceed.
Replacing two files is not a filesystem-wide atomic operation.
"""
import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.services.publications.errors import PublicationError
from app.services.storage import storage_errors as _storage_errors, write_json
from app.services.git.checkout import checkout_lock

PUBLICATION_FILES = ("_publication-v2.json", "_publication.json")


class PublicationStore:
    def __init__(self, work: Path):
        with _storage_errors():
            self.work = Path(work).resolve()
        self.directory = self.work.parent / ".publication-operations" / self.work.name
        self.journal = self.directory / "pending.json"
        self.sync_path = self.directory / "sync.json"

    @contextmanager
    def locked(self):
        with checkout_lock(self.work):
            self.recover()
            yield self

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

    def read_sync(self):
        with _storage_errors():
            return json.loads(self.sync_path.read_text()) if self.sync_path.exists() else None

    def write_sync(self, state):
        write_json(self.sync_path, state)

    def save(self, v2, legacy, user=None):
        pending = dict(zip(PUBLICATION_FILES, (v2, legacy)))
        if user is not None:
            pending["sync"] = {
                "generation": str(uuid4()),
                "user": {key: value for key, value in user.items()
                         if key in ("github_id", "username", "email", "avatar_url", "role")},
                "status": "pending",
                "task_id": None, "dispatch_after": 0, "error": "",
            }
        write_json(self.journal, pending)
        self._apply(pending)
        return pending.get("sync")

    def _apply(self, pending):
        for name in PUBLICATION_FILES:
            write_json(self.work / name, pending[name])
        if "sync" in pending:
            self.write_sync(pending["sync"])
        write_json(self.journal, None)
