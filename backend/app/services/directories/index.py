"""
Shared index of physical navigation directories.

All directory mutations use the same PostgreSQL advisory lock as index readers.
The committed dirty marker survives a failed update or an interrupted process;
the next reader rebuilds before serving results. No per-process cache or TTL is
involved. File contents and immediate child counts remain filesystem reads.
"""

import hashlib
import os
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import delete, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.text_types import TextType
from app.db import database
from app.db.models.directory_index import DirectoryIndexEntry, DirectoryIndexState


class DirectoryIndex:
    def __init__(self, work_directory: Path | None = None):
        self.root = (work_directory or settings.WORK_DIR).resolve()
        self.key = str(self.root)
        self.text_types = {item.value for item in TextType}
        self.lock_id = int.from_bytes(
            hashlib.sha256(f"directory-index:{self.key}".encode()).digest()[:8],
            "big", signed=True,
        )

    @contextmanager
    def _locked(self) -> Generator[Session, None, None]:
        # Pin the connection: a session-level advisory lock must survive the
        # dirty-marker commit and be released before returning to the pool.
        with database.engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": self.lock_id})
            connection.commit()
            try:
                with Session(bind=connection) as session:
                    yield session
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self.lock_id})
                connection.commit()

    def search(self, name: str, exact: bool = False) -> list[Path]:
        with self._locked() as session:
            state = session.get(DirectoryIndexState, self.key)
            if state is None or not state.ready:
                self._rebuild(session)
                self._set_ready(session, True)
                session.commit()
            predicate = (
                DirectoryIndexEntry.name == name if exact
                else DirectoryIndexEntry.search_name.contains(name.lower(), autoescape=True)
            )
            paths = session.scalars(select(DirectoryIndexEntry.path).where(
                DirectoryIndexEntry.work_directory == self.key, predicate,
            )).all()
        return [self.root / path for path in paths]

    def rebuild(self) -> None:
        with self._locked() as session:
            self._set_ready(session, False)
            session.commit()
            self._rebuild(session)
            self._set_ready(session, True)
            session.commit()

    @contextmanager
    def changes(self, directories: Iterable[Path], *, recursive: bool = False) -> Generator[None, None, None]:
        """Synchronize actual directories, including partial filesystem failures.

        Creation only needs its ancestor chain; deletion and Git checkout need
        to reconcile entire affected subtrees. Passing the work root rebuilds.
        """
        paths = {self._relative(path) for path in directories}
        paths = {path for path in paths if path == Path('.') or self._allowed(path)}
        if not paths:
            yield
            return

        with self._locked() as session:
            state = session.get(DirectoryIndexState, self.key)
            was_ready = state is not None and state.ready
            self._set_ready(session, False)
            session.commit()
            try:
                yield
            finally:
                if not was_ready or Path('.') in paths:
                    self._rebuild(session)
                else:
                    self._synchronize(session, paths, recursive=recursive)
                self._set_ready(session, True)
                session.commit()

    def _relative(self, path: Path) -> Path:
        path = Path(os.path.abspath(path))
        # Resolve the work root (which may itself be a symlink), but do not
        # follow directory symlinks inside the repository.
        logical_root = Path(os.path.abspath(settings.WORK_DIR))
        if logical_root.resolve() == self.root and path.is_relative_to(logical_root):
            return path.relative_to(logical_root)
        return path.relative_to(self.root)

    def _allowed(self, path: Path) -> bool:
        return bool(path.parts) and path.parts[0] in self.text_types and all(
            not part.startswith('.') for part in path.parts
        )

    def _physical_directory(self, path: Path) -> bool:
        return all(
            not (self.root / parent).is_symlink()
            for parent in (path, *path.parents)
        ) and (self.root / path).is_dir()

    def _walk(self, path: Path) -> Iterator[Path]:
        if not self._physical_directory(path):
            return
        pending = [path]
        while pending:
            current = pending.pop()
            if len(current.parts) > 1:
                yield current
            with os.scandir(self.root / current) as entries:
                pending.extend(
                    current / entry.name for entry in entries
                    if not entry.name.startswith('.') and entry.is_dir(follow_symlinks=False)
                )

    def _store(self, session: Session, paths: Iterable[Path]) -> None:
        rows = [
            {"work_directory": self.key, "path": path.as_posix(),
             "name": path.name, "search_name": path.name.lower()}
            for path in set(paths) if len(path.parts) > 1
        ]
        if rows:
            session.execute(insert(DirectoryIndexEntry).on_conflict_do_nothing(), rows)

    def _set_ready(self, session: Session, ready: bool) -> None:
        session.execute(insert(DirectoryIndexState).values(
            work_directory=self.key, ready=ready,
        ).on_conflict_do_update(
            index_elements=[DirectoryIndexState.work_directory], set_={"ready": ready},
        ))

    def _rebuild(self, session: Session) -> None:
        # A missing/unreadable checkout is an error, not an empty valid index.
        if not self.root.is_dir():
            raise FileNotFoundError(self.root)
        paths = [path for kind in self.text_types for path in self._walk(Path(kind))]
        session.execute(delete(DirectoryIndexEntry).where(
            DirectoryIndexEntry.work_directory == self.key,
        ))
        self._store(session, paths)

    def _synchronize(self, session: Session, paths: set[Path], *, recursive: bool) -> None:
        # Avoid rescanning descendants when an ancestor is already affected.
        roots = (
            {path for path in paths if not any(parent in paths for parent in path.parents)}
            if recursive else paths
        )
        found = set()
        for path in roots:
            if recursive:
                self._remove(session, path)
                found.update(self._walk(path))
            for ancestor in (path, *path.parents):
                if not self._allowed(ancestor):
                    continue
                if self._physical_directory(ancestor):
                    found.add(ancestor)
                else:
                    self._remove(session, ancestor)
        self._store(session, found)

    def _remove(self, session: Session, path: Path) -> None:
        session.execute(delete(DirectoryIndexEntry).where(
            DirectoryIndexEntry.work_directory == self.key,
            or_(DirectoryIndexEntry.path == path.as_posix(),
                DirectoryIndexEntry.path.startswith(path.as_posix() + '/', autoescape=True)),
        ))


def create_indexed_directory(path: Path) -> None:
    """Create a directory tree and index every physical ancestor it introduces."""
    index = DirectoryIndex()
    with index.changes([path]):
        path.mkdir(parents=True, exist_ok=True)
