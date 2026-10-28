"""Bulk notification metadata and bounded, shared immutable Git query caches."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from app.core.config import settings
from app.services.notifications.git_query import run


class FeedUnavailable(Exception):
    pass


class QueryCache:
    """Disk cache shared by web workers; never store user/read/time-relative data."""

    def __init__(self, directory, max_bytes=32 * 1024 * 1024, max_entry_bytes=2 * 1024 * 1024,
                 max_entries=256):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.max_entry_bytes = max_entry_bytes
        self.max_entries = max_entries

    @contextmanager
    def locked(self):
        with (self.directory / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # A killed writer may leave its atomic-write temporary file behind.
            for pending in self.directory.glob('.query-*'):
                pending.unlink()
            yield

    def get_or_load(self, key, load):
        path = self.directory / (hashlib.sha256(key.encode()).hexdigest() + '.json')
        with self.locked():
            if path.exists():
                try:
                    value = json.loads(path.read_text())
                except json.JSONDecodeError:
                    path.unlink()
                else:
                    os.utime(path, None)
                    return value
        # Do not serialize unrelated Git queries behind cache I/O. A concurrent
        # cold miss can compute the same immutable value; publication is atomic.
        value = load()
        data = json.dumps(value, ensure_ascii=False).encode()
        if len(data) > min(self.max_entry_bytes, self.max_bytes):
            return value
        with self.locked():
            path.unlink(missing_ok=True)
            entries = sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime_ns)
            total = sum(p.stat().st_size for p in entries)
            while entries and (total + len(data) > self.max_bytes or len(entries) >= self.max_entries):
                oldest = entries.pop(0)
                total -= oldest.stat().st_size
                oldest.unlink()
            fd, name = tempfile.mkstemp(dir=self.directory, prefix='.query-')
            try:
                with os.fdopen(fd, 'wb') as output:
                    output.write(data)
                os.replace(name, path)
            finally:
                Path(name).unlink(missing_ok=True)
        return value


class NotificationFeed:
    def __init__(self, directory):
        self.cache = QueryCache(directory)

    @staticmethod
    def git(repository, *args):
        command = ['git', '--no-replace-objects', '-c', f'safe.directory={repository}',
                   '-c', 'core.quotepath=false', *args]
        try:
            result = run(command, cwd=repository, timeout=settings.NOTIFICATION_GIT_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise FeedUnavailable('Unable to read Git notifications') from error
        if result.returncode:
            raise FeedUnavailable('Unable to read Git notifications')
        return result.stdout.decode('utf-8', errors='replace')

    def metadata(self, repository, days):
        # No per-commit subprocesses. Keep relative text fresh on each request.
        output = self.git(repository, 'log', '-z', '--no-merges', '--date=default',
                          '--format=%H%x00%h%x00%an <%ae>%x00%ad%x00%s%x00%cr',
                          f'--since={days} days ago', 'HEAD', '--')
        fields = output.removesuffix('\0').split('\0') if output else []
        if len(fields) % 6:
            raise FeedUnavailable('Invalid Git notification metadata')
        rows = []
        for index in range(0, len(fields), 6):
            oid, short, author, date, subject, relative = fields[index:index + 6]
            info = f'{short} {subject} ({relative})'
            # Preserve the public fields/abbreviated read IDs used by existing clients.
            parts = info.split(' ', 3)
            rows.append({'_oid': oid, 'commit': short, 'author': author, 'date': date,
                         'info': info, 'message': ' '.join(parts[1:3])})
        return rows

    def details(self, repository, oid):
        def load():
            paths = self.git(repository, 'diff-tree', '--root', '--no-commit-id',
                             '--name-only', '-r', '-z', '--find-renames=50%', oid, '--')
            patch = self.git(repository, 'show', '--format=', '--no-notes', '--no-color',
                             '--no-ext-diff', '--no-textconv', '--find-renames=50%',
                             '--diff-algorithm=myers', '--src-prefix=a/', '--dst-prefix=b/',
                             oid, '--')
            return {'paths': [p for p in paths.split('\0') if p.endswith('.json')],
                    'patch': patch}
        return self.cache.get_or_load(f'detail-v1:{Path(repository).resolve()}:{oid}', load)

    def authors(self, repository):
        # Include every ref and detached HEAD. Freeze OIDs before the history
        # query so a concurrent ref update cannot populate the wrong cache key.
        tips = sorted(set(self.git(repository, 'rev-parse', '--revs-only', '--all', 'HEAD').splitlines()))
        def load():
            authors = set()
            # Bound argv size even in repositories with very many refs. Git
            # groups raw %an names (without mailmap); Python sees unique groups.
            for start in range(0, len(tips), 256):
                output = self.git(repository, 'shortlog', '-s', '--group=format:%an',
                                  *tips[start:start + 256], '--')
                authors.update(line.split('\t', 1)[1].strip()
                               for line in output.splitlines() if '\t' in line)
            return sorted(author for author in authors if author)
        version = hashlib.sha256('\n'.join(tips).encode()).hexdigest()
        return self.cache.get_or_load(f'authors-v1:{Path(repository).resolve()}:{version}', load)


feed_service = NotificationFeed(settings.NOTIFICATION_HISTORY_DIR / 'feed')
