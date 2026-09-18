"""Durable redo journal and cross-process coordination for one root text.

Callers hold lock(shared=True) for reads and lock() for writes. A
prepared operation blocks ordinary reads/writes until the same operation resumes.
This is a recoverable multi-file commit, not a claim of filesystem-wide atomicity.
"""
import fcntl
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from app.services.projects.structure_engine import digest


class StructureConflict(ValueError):
    pass


class StructureStore:
    def __init__(self, work, root):
        self.work = Path(work).resolve()
        self.root = Path(root).resolve()
        self.root.relative_to(self.work)
        self.directory = self.work.parent / '.structure-operations' / digest(str(self.root))

    @contextmanager
    def lock(self, name='lock', *, shared=False):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / name).open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            try:
                yield self
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def write_json(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
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

    def get(self, operation_id):
        path = self.directory / f'{UUID(str(operation_id))}.json'
        return json.loads(path.read_text()) if path.exists() else None

    def pending(self):
        path = self.directory / 'pending.json'
        return json.loads(path.read_text()) if path.exists() else None

    def check_ready(self):
        pending = self.pending()
        if pending:
            raise StructureConflict(f"Structure operation {pending['operation_id']} is pending. Resume it before editing.")

    def revision(self, root_data=None):
        """Use a caller's lock-scoped Root snapshot when it is already loaded."""
        head = self.directory / 'head.json'
        epoch = json.loads(head.read_text()) if head.exists() else None
        if root_data is None:
            root_data = json.loads(self.root.read_text())
        return digest([list(root_data), epoch])

    def check_revision(self, revision, root_data=None):
        if revision is not None and revision != self.revision(root_data):
            raise StructureConflict('The text structure has changed. Reload before saving.')
        if revision is None and (self.directory / 'head.json').exists():
            raise StructureConflict('A structure version is required. Reload before saving.')

    def prepare(self, record):
        self.check_ready()
        self.write_json(self.directory / 'pending.json', record)

    def apply(self, record):
        for relative, data in record['files'].items():
            target = (self.work / relative).resolve()
            target.relative_to(self.work)
            self.write_json(target, data)

    def finish(self, record, result):
        self.write_json(self.directory / 'head.json', record['operation_id'])
        # Include the committed epoch even if keys return to an earlier layout.
        result['structure_revision'] = self.revision()
        self.write_json(self.directory / f"{UUID(record['operation_id'])}.json", {**record, 'result': result})
        self.write_json(self.directory / 'pending.json', None)
