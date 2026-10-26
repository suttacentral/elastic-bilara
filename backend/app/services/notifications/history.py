"""Bounded Git history shared by all web workers in one backend container.

flock locks must live on the same local filesystem for every worker.

Client interest is a separate shared lock, so an owner's disconnected client does not
cancel a query still needed by another worker.

Locks are released by the kernel on worker death. Cache entries contain no user preferences or read state.
"""
import asyncio
from contextlib import suppress
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
from uuid import uuid4

from app.core.config import settings


class HistoryUnavailable(Exception):
    pass


class HistoryBusy(HistoryUnavailable):
    pass


class HistoryTimeout(HistoryUnavailable):
    pass


def _lock(path, shared=False):
    handle = open(path, "a+b")
    try:
        fcntl.flock(handle, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def _read(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        # Recompute invalid JSON under the existing owner lock; a successful
        # query replaces it atomically. Keep filesystem failures visible.
        return None


def _write(path, data):
    # Readers always see a complete snapshot, including across worker processes.
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".history-")
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(data, output)
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


class NotificationHistory:
    def __init__(self, directory, concurrency=2, capacity=32, timeout=15, queue_timeout=5):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.concurrency = concurrency
        self.capacity = capacity
        self.timeout = timeout
        self.queue_timeout = queue_timeout
        self.tasks = {}
        self.closing = set()
        self._draining = set()

    def _slot(self, kind, count):
        for index in range(count):
            handle = _lock(self.directory / f"{kind}-{index}.lock")
            if handle is not None:
                return handle
        return None

    async def _acquire_state(self, key):
        # Ordinary cross-worker registration/probe contention is not overload.
        # Keep the wait cancellable and bounded, without blocking the event loop.
        deadline = time.monotonic() + self.queue_timeout
        while time.monotonic() < deadline:
            state = _lock(self.directory / f"{key}.state")
            if state is not None:
                return state
            remaining = deadline - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(min(0.01, remaining))
        raise HistoryBusy("Notification query state wait timed out")

    async def history(self, repository, days):
        # Bound *all* admitted clients, including callers joining shared work.
        admission = self._slot("client", self.capacity)
        if admission is None:
            raise HistoryBusy("Notification query capacity reached")
        interest = None
        try:
            now = int(time.time())
            since = now - days * 86400
            lower_bound = since // 86400 * 86400
            identity = f"{Path(repository).resolve()}:{lower_bound}"
            key = hashlib.sha256(identity.encode()).hexdigest()
            state = await self._acquire_state(key)
            try:
                if key in self.closing:
                    raise HistoryBusy("Notification query is finishing; retry")
                interest = _lock(self.directory / f"{key}.interest", shared=True)
                if interest is None:
                    raise HistoryBusy("Notification query is finishing; retry")
                task = self.tasks.get(key)
                if task is None or task.done():
                    task = asyncio.create_task(self._load(repository, lower_bound, key))
                    self.tasks[key] = task
                    task.add_done_callback(lambda done: self._finished(key, done))
            finally:
                state.close()
            rows = await asyncio.shield(task)
            return [(commit, author) for commit, author, timestamp in rows if timestamp >= since]
        finally:
            if interest is not None:
                interest.close()
            admission.close()

    def _finished(self, key, task):
        if self.tasks.get(key) is task:
            self.tasks.pop(key, None)
            self.closing.discard(key)
        # The last client may have gone away; always retrieve task exceptions.
        if not task.cancelled():
            task.exception()

    def _has_clients(self, key):
        # Caller holds .state, serializing registration and all probes. Only
        # clients retain .interest locks; cleanup never masquerades as a client.
        probe = _lock(self.directory / f"{key}.interest")
        if probe is None:
            return True
        probe.close()
        return False

    async def _check_clients(self, key):
        state = await self._acquire_state(key)
        try:
            if not self._has_clients(key):
                self.closing.add(key)
                raise asyncio.CancelledError
        finally:
            state.close()

    async def _watch_clients(self, key, task):
        while not task.done():
            state = _lock(self.directory / f"{key}.state")
            if state is not None:
                try:
                    if not self._has_clients(key):
                        self.closing.add(key)
                        # Block admission and takeover checks until reaping ends.
                        # Keep .interest free so it represents clients only.
                        self._cancel_pending(task)
                        await asyncio.gather(task, return_exceptions=True)
                        return
                finally:
                    state.close()
            await asyncio.sleep(0.05)

    def _cancel_pending(self, task):
        # A second cancel can interrupt a child's awaited process reaping.
        if task not in self._draining and not task.done() and not task.cancelling():
            task.cancel()

    async def _wait_for_query(self, key, awaitable, timeout):
        task = asyncio.ensure_future(awaitable)
        try:
            # asyncio.wait does not cancel the child on timeout or cancellation.
            # Mark the shared job unjoinable before initiating child cleanup.
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if not done:
                raise asyncio.TimeoutError
            return task.result()
        except BaseException:
            self.closing.add(key)
            current = asyncio.current_task()
            self._draining.add(current)
            try:
                self._cancel_pending(task)
                await asyncio.gather(task, return_exceptions=True)
            finally:
                self._draining.discard(current)
            raise

    async def _load(self, repository, lower_bound, key):
        work = asyncio.create_task(self._shared_load(repository, lower_bound, key))
        watcher = asyncio.create_task(self._watch_clients(key, work))
        try:
            # Includes waiting for the other worker and the global execution slot.
            return await self._wait_for_query(key, work, self.queue_timeout + self.timeout)
        except asyncio.TimeoutError as error:
            raise HistoryTimeout("Git notification query timed out") from error
        finally:
            # Keep tracking the job for close(), but reject all new joiners.
            self.closing.add(key)
            self._cancel_pending(work)
            self._cancel_pending(watcher)
            await asyncio.gather(work, watcher, return_exceptions=True)

    async def _shared_load(self, repository, lower_bound, key):
        result_path = self.directory / f"{key}.result"
        initial = _read(result_path)
        generation = initial.get("generation") if initial else None
        owner = None
        while owner is None:
            owner = _lock(self.directory / f"{key}.owner")
            if owner is None:
                await asyncio.sleep(0.05)
        try:
            # A previous owner may have published between our read and lock.
            result = _read(result_path)
            if result and result.get("generation") != generation:
                return self._result(result)
            await self._check_clients(key)
            slot = None
            deadline = time.monotonic() + self.queue_timeout
            while slot is None:
                slot = self._slot("git", self.concurrency)
                if slot is None:
                    if time.monotonic() >= deadline:
                        raise HistoryBusy("Git notification query queue timed out")
                    await asyncio.sleep(0.05)
            try:
                await self._check_clients(key)
                rows = await self._wait_for_query(
                    key, self._snapshot(repository, lower_bound, key), self.timeout
                )
            finally:
                slot.close()
            _write(result_path, {"generation": uuid4().hex, "rows": rows})
            return rows
        except (HistoryUnavailable, asyncio.TimeoutError) as error:
            if isinstance(error, (HistoryTimeout, asyncio.TimeoutError)):
                error_type = "timeout"
            elif isinstance(error, HistoryBusy):
                error_type = "busy"
            else:
                error_type = "unavailable"
            _write(result_path, {"generation": uuid4().hex, "error": error_type})
            if isinstance(error, asyncio.TimeoutError):
                raise HistoryTimeout("Git notification query timed out") from error
            raise
        finally:
            owner.close()

    @staticmethod
    def _result(result):
        if result.get("error") == "timeout":
            raise HistoryTimeout("Git notification query timed out")
        if result.get("error") == "busy":
            raise HistoryBusy("Git notification query queue timed out")
        if result.get("error"):
            raise HistoryUnavailable("Unable to read Git notification history")
        return result["rows"]

    async def _snapshot(self, repository, lower_bound, key):
        await self._check_clients(key)
        revision = (await self._git(repository, "rev-parse", "--verify", "HEAD")).strip()
        cache_path = self.directory / f"{key}.cache"
        cached = _read(cache_path)
        if cached and cached["revision"] == revision:
            return cached["rows"]
        await self._check_clients(key)
        output = await self._git(
            repository, "log", revision, "--pretty=format:%h|%ct|%an <%ae>",
            f"--since=@{lower_bound}", "--no-merges",
        )
        rows = []
        for line in output.splitlines():
            if line:
                commit, timestamp, author = line.split("|", 2)
                rows.append((commit, author, int(timestamp)))
        _write(cache_path, {"revision": revision, "rows": rows})
        # Expire old history payloads. Lock files are deliberately never
        # unlinked: replacing a lock inode would break exclusion across workers.
        payloads = sorted(self.directory.glob("*.cache"), key=lambda p: p.name)
        for path in payloads:
            if path != cache_path:
                with suppress(FileNotFoundError):
                    if path.stat().st_mtime < time.time() - 86400:
                        path.unlink()
                        path.with_suffix(".result").unlink(missing_ok=True)
        return rows

    async def _git(self, repository, *arguments):
        command = ["git", "-c", f"safe.directory={repository}", *arguments]
        # A tiny exec wrapper also kills Git if its owning worker is SIGKILLed.
        launcher = Path(__file__).with_name("git_child.py")
        process = None
        launch = asyncio.create_task(asyncio.create_subprocess_exec(
            sys.executable, str(launcher), str(os.getpid()), *command,
            cwd=repository, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, start_new_session=True,
        ))
        try:
            # Do not lose the PID if cancellation arrives during subprocess spawn.
            process = await asyncio.shield(launch)
            stdout, _ = await process.communicate()
            if process.returncode:
                raise HistoryUnavailable("Unable to read Git notification history")
            return stdout.decode("utf-8", errors="replace")
        except OSError as error:
            raise HistoryUnavailable("Unable to read Git notification history") from error
        finally:
            if process is None:
                with suppress(OSError):
                    process = await launch
            if process is not None:
                # Kill the session even if Git exited but a descendant kept pipes open.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()

    async def close(self):
        jobs = list(self.tasks.items())
        for key, task in jobs:
            if key not in self.closing:
                self.closing.add(key)
                self._cancel_pending(task)
        # Already-retiring jobs still own resources. Drain them without another
        # cancellation that could interrupt their cleanup or change their result.
        await asyncio.gather(*(task for _, task in jobs), return_exceptions=True)


history_service = NotificationHistory(
    settings.NOTIFICATION_HISTORY_DIR,
    concurrency=settings.NOTIFICATION_GIT_CONCURRENCY,
    capacity=settings.NOTIFICATION_QUERY_CAPACITY,
    timeout=settings.NOTIFICATION_GIT_TIMEOUT,
    queue_timeout=settings.NOTIFICATION_QUERY_WAIT_TIMEOUT,
)
