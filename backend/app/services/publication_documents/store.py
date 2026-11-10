"""Recoverable, byte-preserving saves and durable per-publication task intents."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from app.services.git.checkout import checkout_lock
from app.services.publication_documents.catalog import confined_path
from app.services.publications.errors import PublicationError
from app.services.storage import storage_errors, write_json


def revision(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def read_html(path):
    with storage_errors():
        try:
            # read_text uses universal newlines. Preserve CRLF and the final newline exactly.
            return path.read_bytes().decode("utf-8")
        except UnicodeError as exc:
            raise PublicationError(422, "Publication HTML must be UTF-8 encoded.") from exc


def write_html(path, content):
    with storage_errors():
        mode = stat.S_IMODE(path.stat().st_mode)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content.encode("utf-8"))
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


def operations_root(work):
    work = Path(work).resolve()
    return work.parent / ".publication-document-operations" / work.name


class DocumentStore:
    def __init__(self, work, number, operation="sync"):
        if not re.fullmatch(r"scpub[1-9]\d*", number):
            raise PublicationError(404, "Publication not found.")
        self.work = Path(work).resolve()
        self.number = number
        self.operation = operation
        self.directory = operations_root(self.work) / number
        self.state_path = self.directory / "state.json"
        self.journal = self.directory / "pending.json"

    @contextmanager
    def locked(self):
        with checkout_lock(self.work):
            with storage_errors():
                self.directory.mkdir(parents=True, exist_ok=True)
            self.recover()
            yield self

    def read(self):
        with storage_errors():
            return json.loads(self.state_path.read_text()) if self.state_path.exists() else {
                "documents": {}, "sync": None, "publish": None,
            }

    def write(self, state):
        write_json(self.state_path, state)

    def read_sync(self):
        return self.read()[self.operation]

    def write_sync(self, task):
        state = self.read()
        state[self.operation] = task
        self.write(state)

    def save(self, path, content, state):
        pending = {"path": path, "content": content, "state": state}
        write_json(self.journal, pending)
        self._apply(pending)

    def recover(self):
        with storage_errors():
            pending = json.loads(self.journal.read_text()) if self.journal.exists() else None
        if pending:
            self._apply(pending)

    def _apply(self, pending):
        write_html(confined_path(self.work, pending["path"], html=True), pending["content"])
        self.write(pending["state"])
        write_json(self.journal, None)


def recover_all(work):
    with checkout_lock(work):
        for directory in operations_root(work).glob("scpub*"):
            if directory.is_dir() and re.fullmatch(r"scpub[1-9]\d*", directory.name):
                DocumentStore(work, directory.name).recover()
