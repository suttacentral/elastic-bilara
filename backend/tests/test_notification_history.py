import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.notifications.history import (
    HistoryBusy, HistoryTimeout, HistoryUnavailable, NotificationHistory,
)


@pytest.fixture
def fake_git(tmp_path, monkeypatch):
    binary = tmp_path / 'bin'
    binary.mkdir()
    git = binary / 'git'
    git.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
root = pathlib.Path.cwd()
operation = 'log' if 'log' in sys.argv else 'rev-parse'
def event(kind):
    with (root / 'events').open('a') as f:
        f.write(json.dumps([kind, operation, os.getpid(), time.monotonic()]) + '\\n')
event('start')
if operation == 'rev-parse':
    print((root / 'revision').read_text())
else:
    time.sleep(float((root / 'delay').read_text()))
    if (root / 'fail').exists():
        sys.exit(128)
    print((root / 'rows').read_text())
event('end')
''')
    git.chmod(0o755)
    monkeypatch.setenv('PATH', f'{binary}:{os.environ["PATH"]}')
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'revision').write_text('a' * 40)
    (repo / 'delay').write_text('0.3')
    (repo / 'rows').write_text(f'abc1234|{int(time.time())}|Selected <selected@example.com>')
    return repo


def events(repo):
    path = repo / 'events'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


async def wait_for(predicate):
    for _ in range(300):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError('condition not reached')


def starts(repo):
    return [e for e in events(repo) if e[:2] == ['start', 'log']]


def assert_reaped(pid):
    assert not Path(f'/proc/{pid}').exists(), f'process {pid} survived or is a zombie'


def test_shared_query_cancel_cache_and_revision(tmp_path, fake_git):
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        try:
            first = asyncio.create_task(service.history(fake_git, 30))
            second = asyncio.create_task(service.history(fake_git, 30))
            await wait_for(lambda: starts(fake_git))
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            assert await second == [('abc1234', 'Selected <selected@example.com>')]
            assert len(starts(fake_git)) == 1
            assert await service.history(fake_git, 30)
            assert len(starts(fake_git)) == 1  # same revision and range
            (fake_git / 'revision').write_text('b' * 40)
            assert await service.history(fake_git, 30)
            assert len(starts(fake_git)) == 2
            assert await service.history(fake_git, 60)
            assert len(starts(fake_git)) == 3
        finally:
            await service.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('action', ['cancel', 'timeout', 'shutdown'])
def test_cleanup_reaps_git_and_releases_slots(tmp_path, fake_git, action):
    (fake_git / 'delay').write_text('60')

    async def scenario():
        service = NotificationHistory(tmp_path / 'cache', concurrency=1, capacity=1, timeout=0.3)
        task = asyncio.create_task(service.history(fake_git, 30))
        await wait_for(lambda: starts(fake_git))
        pid = starts(fake_git)[0][2]
        if action == 'cancel':
            task.cancel()
        elif action == 'shutdown':
            await service.close()
        with pytest.raises(HistoryTimeout if action == 'timeout' else asyncio.CancelledError):
            await task
        await wait_for(lambda: not service.tasks)
        assert_reaped(pid)
        # No client admission lock or execution slot leaked.
        (fake_git / 'delay').write_text('0')
        assert await service.history(fake_git, 30)
        await service.close()
    asyncio.run(scenario())


def test_queue_and_admission_are_bounded_across_instances(tmp_path, fake_git):
    (fake_git / 'delay').write_text('1')

    async def scenario():
        first = NotificationHistory(tmp_path / 'cache', concurrency=1, capacity=2, queue_timeout=0.15)
        second = NotificationHistory(tmp_path / 'cache', concurrency=1, capacity=2, queue_timeout=0.15)
        active = asyncio.create_task(first.history(fake_git, 30))
        await wait_for(lambda: starts(fake_git))
        waiting = asyncio.create_task(second.history(fake_git, 60))
        await asyncio.sleep(0.05)
        with pytest.raises(HistoryBusy):
            await first.history(fake_git, 90)
        with pytest.raises(HistoryBusy):
            await waiting
        assert len(starts(fake_git)) == 1
        await active
        await first.close()
        await second.close()
    asyncio.run(scenario())


def test_nonzero_and_launch_failure_not_cached_as_success(tmp_path, fake_git):
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        (fake_git / 'fail').touch()
        with pytest.raises(HistoryUnavailable):
            await service.history(fake_git, 30)
        (fake_git / 'fail').unlink()
        assert await service.history(fake_git, 30)
        with patch('asyncio.create_subprocess_exec', new=AsyncMock(side_effect=OSError('missing'))):
            with pytest.raises(HistoryUnavailable):
                await service.history(fake_git, 60)
        await service.close()
    asyncio.run(scenario())


# Separate Python interpreters share only the filesystem, as the two web workers do.
WORKER = '''
import asyncio, json, pathlib, sys
from app.services.notifications.history import NotificationHistory
async def main():
    cache, repo, role = sys.argv[1:]
    service = NotificationHistory(cache, concurrency=1, capacity=3)
    task = asyncio.create_task(service.history(repo, 30))
    await asyncio.sleep(.1)
    pathlib.Path(repo, role + '-ready').touch()
    if role == 'owner':
        while not pathlib.Path(repo, 'cancel').exists():
            await asyncio.sleep(.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        while service.tasks:
            await asyncio.sleep(.01)
        print('cancelled', flush=True)
    else:
        print(json.dumps(await task), flush=True)
    await service.close()
asyncio.run(main())
'''


def test_two_workers_merge_and_owner_disconnect_preserves_follower(tmp_path, fake_git):
    (fake_git / 'delay').write_text('1')

    async def scenario():
        processes = []
        try:
            owner = await asyncio.create_subprocess_exec(
                sys.executable, '-c', WORKER, str(tmp_path / 'cache'), str(fake_git), 'owner',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            processes.append(owner)
            await wait_for(lambda: starts(fake_git))
            follower = await asyncio.create_subprocess_exec(
                sys.executable, '-c', WORKER, str(tmp_path / 'cache'), str(fake_git), 'follower',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            processes.append(follower)
            await wait_for(lambda: (fake_git / 'follower-ready').exists())
            (fake_git / 'cancel').touch()
            owner_output, follower_output = await asyncio.wait_for(
                asyncio.gather(owner.communicate(), follower.communicate()), 5
            )
            assert owner.returncode == follower.returncode == 0, (owner_output, follower_output)
            assert owner_output[0].strip() == b'cancelled'
            assert json.loads(follower_output[0]) == [['abc1234', 'Selected <selected@example.com>']]
            assert len(starts(fake_git)) == 1
            assert_reaped(starts(fake_git)[0][2])
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
                await process.wait()
    asyncio.run(scenario())


def test_real_git_full_history_and_time_window(tmp_path):
    repo = tmp_path / 'real-repo'
    repo.mkdir()
    def git(*args, env=None):
        return subprocess.check_output(['git', '-C', str(repo), *args], env=env, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Selected')
    git('config', 'user.email', 'selected@example.com')
    timestamp = int(time.time())
    old_env = dict(os.environ, GIT_COMMITTER_DATE=f'@{timestamp - 31 * 86400} +0000',
                   GIT_AUTHOR_DATE=f'@{timestamp - 31 * 86400} +0000')
    git('commit', '--allow-empty', '-m', 'old', env=old_env)
    for i in range(105):
        git('commit', '--allow-empty', '-qm', str(i))
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        assert len(await service.history(repo, 30)) == 105
        assert len(await service.history(repo, 60)) == 106
        git('commit', '--allow-empty', '-qm', 'new')
        assert len(await service.history(repo, 30)) == 106
        await service.close()
    asyncio.run(scenario())


def test_cancellation_during_spawn_still_reaps_child(tmp_path, fake_git):
    (fake_git / 'delay').write_text('60')
    real_spawn = asyncio.create_subprocess_exec
    spawned = []

    async def delayed_spawn(*args, **kwargs):
        process = await real_spawn(*args, **kwargs)
        spawned.append(process)
        await asyncio.sleep(0.2)
        return process

    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        with patch('asyncio.create_subprocess_exec', side_effect=delayed_spawn):
            task = asyncio.create_task(service._git(fake_git, 'log'))
            await wait_for(lambda: spawned)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert_reaped(spawned[0].pid)
        await service.close()
    asyncio.run(scenario())


BUDGET_WORKER = '''
import asyncio, json, pathlib, sys
from app.services.notifications.history import HistoryBusy, NotificationHistory
async def main():
    cache, repo, number = sys.argv[1:]
    service = NotificationHistory(cache, concurrency=2, capacity=3)
    pathlib.Path(repo, number + '-ready').touch()
    while not pathlib.Path(repo, 'go').exists():
        await asyncio.sleep(.01)
    async def query(days):
        try:
            await service.history(repo, days)
            return 'ok'
        except HistoryBusy:
            return 'busy'
    print(json.dumps(await asyncio.gather(query(30 + int(number)), query(60 + int(number)))))
    await service.close()
asyncio.run(main())
'''


def test_two_worker_total_concurrency_and_capacity(tmp_path, fake_git):
    (fake_git / 'delay').write_text('0.5')

    async def scenario():
        processes = []
        try:
            for number in ('1', '2'):
                processes.append(await asyncio.create_subprocess_exec(
                    sys.executable, '-c', BUDGET_WORKER,
                    str(tmp_path / 'cache'), str(fake_git), number,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                ))
            await wait_for(lambda: all((fake_git / f'{n}-ready').exists() for n in ('1', '2')))
            (fake_git / 'go').touch()
            output = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in processes)), 5)
            assert all(p.returncode == 0 for p in processes), output
            results = [status for stdout, _ in output for status in json.loads(stdout)]
            assert sorted(results) == ['busy', 'ok', 'ok', 'ok']
            running = peak = 0
            for kind, _, _, _ in sorted(events(fake_git), key=lambda event: event[3]):
                running += 1 if kind == 'start' else -1
                peak = max(peak, running)
            assert peak == 2
            assert running == 0
            assert len(starts(fake_git)) == 3
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
                await process.wait()
    asyncio.run(scenario())


def test_cached_range_filters_rolling_cutoff(tmp_path, fake_git):
    now = int(time.time())
    cutoff = now - 30 * 86400
    (fake_git / 'rows').write_text(f'old|{cutoff - 1}|Selected\nnew|{cutoff + 1}|Selected')

    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        with patch('app.services.notifications.history.time.time', return_value=now):
            assert await service.history(fake_git, 30) == [('new', 'Selected')]
        with patch('app.services.notifications.history.time.time', return_value=now + 2):
            assert await service.history(fake_git, 30) == []
        assert len(starts(fake_git)) == 1
        await service.close()
    asyncio.run(scenario())


def test_worker_death_terminates_git(tmp_path, fake_git):
    (fake_git / 'delay').write_text('60')
    # A separate test supervisor adopts/reaps the orphan, without changing the
    # pytest process or depending on the container's PID 1 reaping behavior.
    supervisor = '''
import ctypes, json, os, pathlib, signal, subprocess, sys, time
assert ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
code = "import asyncio, sys; from app.services.notifications.history import NotificationHistory; asyncio.run(NotificationHistory(sys.argv[1]).history(sys.argv[2], 30))"
worker = subprocess.Popen([sys.executable, '-c', code, sys.argv[1], sys.argv[2]])
pid = guardian = None
try:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        path = pathlib.Path(sys.argv[2], 'events')
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        logs = [row for row in rows if row[:2] == ['start', 'log']]
        if logs:
            pid = logs[0][2]
            break
        time.sleep(.01)
    assert pid is not None
    status = pathlib.Path(f"/proc/{pid}/status").read_text()
    guardian = int(next(line.split()[1] for line in status.splitlines() if line.startswith("PPid:")))
    worker.kill()
    worker.wait(timeout=2)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        reaped, status = os.waitpid(guardian, os.WNOHANG)
        if reaped:
            assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 137
            assert not pathlib.Path(f"/proc/{pid}").exists()
            break
        time.sleep(.01)
    else:
        raise AssertionError('Query guardian did not finish cleanup')
finally:
    if worker.poll() is None:
        worker.kill()
        worker.wait()
    if guardian is not None:
        try:
            os.waitpid(guardian, 0)
        except ChildProcessError:
            pass
'''
    result = subprocess.run(
        [sys.executable, '-c', supervisor, str(tmp_path / 'cache'), str(fake_git)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


DISCONNECT_WORKER = '''
import asyncio, pathlib, sys
from app.services.notifications.history import NotificationHistory
async def main():
    cache, repo, role = sys.argv[1:]
    root = pathlib.Path(repo)
    class Service(NotificationHistory):
        async def _shared_load(self, *args):
            (root / (role + '-ready')).touch()
            return await super()._shared_load(*args)
        async def _watch_clients(self, key, task):
            if role == 'follower':
                # Prove takeover checks work independently of the periodic watcher.
                await asyncio.Future()
            await super()._watch_clients(key, task)
    service = Service(cache)
    client = asyncio.create_task(service.history(repo, 30))
    while not (root / 'disconnect').exists():
        await asyncio.sleep(.005)
    client.cancel()
    await asyncio.gather(client, return_exceptions=True)
    (root / (role + '-disconnected')).touch()
    while service.tasks:
        await asyncio.sleep(.005)
    await service.close()
asyncio.run(main())
'''


def test_two_workers_all_disconnect_does_not_start_follower_git(tmp_path, fake_git):
    (fake_git / 'delay').write_text('60')

    async def scenario():
        processes = []
        try:
            owner = await asyncio.create_subprocess_exec(
                sys.executable, '-c', DISCONNECT_WORKER,
                str(tmp_path / 'cache'), str(fake_git), 'owner',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            processes.append(owner)
            await wait_for(lambda: starts(fake_git))
            initial_starts = [e for e in events(fake_git) if e[0] == 'start']
            follower = await asyncio.create_subprocess_exec(
                sys.executable, '-c', DISCONNECT_WORKER,
                str(tmp_path / 'cache'), str(fake_git), 'follower',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            processes.append(follower)
            await wait_for(lambda: (fake_git / 'follower-ready').exists())
            (fake_git / 'disconnect').touch()
            output = await asyncio.wait_for(
                asyncio.gather(*(process.communicate() for process in processes)), 3
            )
            assert all(process.returncode == 0 for process in processes), output
            assert [e for e in events(fake_git) if e[0] == 'start'] == initial_starts
            for event in initial_starts:
                assert_reaped(event[2])
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
                await process.wait()
    asyncio.run(scenario())


def test_disconnect_while_waiting_for_slot_does_not_start_git(tmp_path, fake_git):
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache', concurrency=1)
        occupied = service._slot('git', 1)
        waiting = asyncio.Event()
        original_slot = service._slot
        def slot(kind, count):
            if kind == 'git':
                waiting.set()
            return original_slot(kind, count)
        service._slot = slot
        async def delayed_watcher(*args):
            await asyncio.Future()
        service._watch_clients = delayed_watcher
        client = asyncio.create_task(service.history(fake_git, 30))
        try:
            await asyncio.wait_for(waiting.wait(), 2)
            client.cancel()
            await asyncio.gather(client, return_exceptions=True)
            occupied.close()
            await wait_for(lambda: not service.tasks)
            assert events(fake_git) == []
            # Retirement does not permanently reject new clients or leak slots.
            (fake_git / 'delay').write_text('0')
            assert await service.history(fake_git, 30)
        finally:
            occupied.close()
            client.cancel()
            await asyncio.gather(client, return_exceptions=True)
            await service.close()
    asyncio.run(scenario())


def test_disconnect_after_revision_lookup_skips_history_scan(tmp_path, fake_git):
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        revision_read = asyncio.Event()
        resume = asyncio.Event()
        original_git = service._git
        async def git(*args, **kwargs):
            result = await original_git(*args, **kwargs)
            if 'rev-parse' in args:
                revision_read.set()
                await resume.wait()
            return result
        async def delayed_watcher(*args):
            await asyncio.Future()
        service._git = git
        service._watch_clients = delayed_watcher
        client = asyncio.create_task(service.history(fake_git, 30))
        try:
            await asyncio.wait_for(revision_read.wait(), 2)
            client.cancel()
            await asyncio.gather(client, return_exceptions=True)
            resume.set()
            await wait_for(lambda: not service.tasks)
            assert starts(fake_git) == []
        finally:
            client.cancel()
            await asyncio.gather(client, return_exceptions=True)
            await service.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('trigger', ['query_timeout', 'total_timeout', 'cancel', 'shutdown'])
def test_retiring_job_rejects_joiners_and_shutdown_drains_it(tmp_path, trigger):
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache', timeout=0.04, queue_timeout=0.04)
        running = asyncio.Event()
        cleaning = asyncio.Event()
        release = asyncio.Event()
        cleaned = asyncio.Event()
        interrupted = False
        async def blocked_work(*args):
            nonlocal interrupted
            running.set()
            try:
                await asyncio.Future()
            finally:
                cleaning.set()
                try:
                    await release.wait()
                    cleaned.set()
                except asyncio.CancelledError:
                    interrupted = True
                    raise
        if trigger == 'total_timeout':
            service._shared_load = blocked_work
        else:
            service._snapshot = blocked_work
        first = asyncio.create_task(service.history(tmp_path, 30))
        shutdown = None
        try:
            await asyncio.wait_for(running.wait(), 2)
            key, job = next(iter(service.tasks.items()))
            if trigger == 'cancel':
                job.cancel()
            elif trigger == 'shutdown':
                shutdown = asyncio.create_task(service.close())
            await asyncio.wait_for(cleaning.wait(), 2)
            # New callers must not inherit the retiring job's timeout/cancellation.
            with pytest.raises(HistoryBusy):
                await asyncio.wait_for(service.history(tmp_path, 30), 0.2)
            assert service.tasks[key] is job
            if shutdown is None:
                shutdown = asyncio.create_task(service.close())
            # Outlive both deadlines: the outer timeout must not cancel an
            # inner job a second time while it is draining its child.
            await asyncio.sleep(0.12)
            assert not shutdown.done()
            assert not interrupted
            assert service.tasks[key] is job
            release.set()
            results = await asyncio.gather(first, shutdown, return_exceptions=True)
            expected = HistoryTimeout if 'timeout' in trigger else asyncio.CancelledError
            assert isinstance(results[0], expected)
            assert results[1] is None
            assert cleaned.is_set()
            assert not service.tasks
            assert not service.closing
        finally:
            release.set()
            await asyncio.gather(first, return_exceptions=True)
            if shutdown is not None:
                await shutdown
            await service.close()
    asyncio.run(scenario())


def test_failed_job_cannot_be_joined_during_outer_cleanup(tmp_path):
    async def scenario():
        service = NotificationHistory(tmp_path / 'cache')
        cleaning = asyncio.Event()
        release = asyncio.Event()
        async def failure(*args):
            raise HistoryUnavailable('Git failed')
        async def watcher(*args):
            try:
                await asyncio.Future()
            finally:
                cleaning.set()
                await release.wait()
        service._snapshot = failure
        service._watch_clients = watcher
        first = asyncio.create_task(service.history(tmp_path, 30))
        try:
            await asyncio.wait_for(cleaning.wait(), 2)
            with pytest.raises(HistoryBusy):
                await asyncio.wait_for(service.history(tmp_path, 30), 0.2)
            release.set()
            with pytest.raises(HistoryUnavailable):
                await first
            await wait_for(lambda: not service.tasks)
            service._snapshot = AsyncMock(return_value=[])
            assert await service.history(tmp_path, 30) == []
        finally:
            release.set()
            await asyncio.gather(first, return_exceptions=True)
            await service.close()
    asyncio.run(scenario())



@pytest.mark.parametrize('suffix', ['cache', 'result'])
@pytest.mark.parametrize('broken_json', ['', '{"rows":'])
def test_corrupt_history_json_is_rebuilt_and_reusable(tmp_path, fake_git, suffix, broken_json):
    async def scenario():
        directory = tmp_path / 'cache'
        service = NotificationHistory(directory)
        (fake_git / 'delay').write_text('0')
        try:
            expected = await service.history(fake_git, 30)
            assert expected == [('abc1234', 'Selected <selected@example.com>')]
            path, = directory.glob(f'*.{suffix}')
            path.write_text(broken_json)
            assert await service.history(fake_git, 30) == expected
            restored = json.loads(path.read_text())
            assert restored['rows'][0][:2] == list(expected[0])
            scans = len(starts(fake_git))
            assert scans == (2 if suffix == 'cache' else 1)
            # A later request uses the repaired metadata instead of rescanning.
            assert await service.history(fake_git, 30) == expected
            assert len(starts(fake_git)) == scans
        finally:
            await service.close()
    asyncio.run(scenario())


def test_cache_permission_error_is_not_treated_as_a_miss(tmp_path):
    from app.services.notifications.history import _read

    with patch.object(Path, 'read_text', side_effect=PermissionError('denied')):
        with pytest.raises(PermissionError, match='denied'):
            _read(tmp_path / 'history.cache')


def state_path_for(service, repository, days):
    import hashlib
    lower_bound = (int(time.time()) - days * 86400) // 86400 * 86400
    key = hashlib.sha256(f'{Path(repository).resolve()}:{lower_bound}'.encode()).hexdigest()
    return service.directory / f'{key}.state'


@pytest.mark.parametrize('outcome', ['release', 'timeout', 'cancel'])
def test_state_wait_is_bounded_cancellable_and_keeps_admission_budget(tmp_path, outcome):
    from app.services.notifications import history as module

    async def scenario():
        service = NotificationHistory(tmp_path / 'cache', capacity=1, queue_timeout=0.12)
        service._snapshot = AsyncMock(return_value=[])
        path = state_path_for(service, tmp_path, 30)
        held = module._lock(path)
        waiting = asyncio.Event()
        real_lock = module._lock
        def observed_lock(lock_path, shared=False):
            handle = real_lock(lock_path, shared)
            if lock_path == path and handle is None:
                waiting.set()
            return handle
        first = None
        try:
            with patch.object(module, '_lock', side_effect=observed_lock):
                first = asyncio.create_task(service.history(tmp_path, 30))
                await asyncio.wait_for(waiting.wait(), 1)
                await asyncio.sleep(0.02)  # the event loop remains responsive
                assert not first.done()
                # Even before registration, waiting requests consume capacity.
                with pytest.raises(HistoryBusy, match='capacity'):
                    await service.history(tmp_path, 60)
                if outcome == 'release':
                    held.close()
                    assert await asyncio.wait_for(first, 1) == []
                elif outcome == 'timeout':
                    with pytest.raises(HistoryBusy, match='state wait timed out'):
                        await asyncio.wait_for(first, 1)
                    service._snapshot.assert_not_awaited()
                else:
                    first.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await first
                    service._snapshot.assert_not_awaited()
            held.close()
            # Timeout/cancellation must release admission without starting a job.
            assert await service.history(tmp_path, 30) == []
        finally:
            held.close()
            if first is not None:
                first.cancel()
                await asyncio.gather(first, return_exceptions=True)
            await service.close()
    asyncio.run(scenario())


STATE_CONTENTION_WORKER = '''
import asyncio, json, pathlib, sys
from app.services.notifications import history as module
async def main():
    cache, repo, number = sys.argv[1:]
    original_lock = module._lock
    def observed_lock(path, shared=False):
        handle = original_lock(path, shared)
        if path.suffix == '.state' and handle is None:
            pathlib.Path(repo, number + '-waiting').touch()
        return handle
    module._lock = observed_lock
    service = module.NotificationHistory(cache, concurrency=2, capacity=10)
    try:
        rows = await service.history(repo, 30)
        print(json.dumps({'rows': rows}), flush=True)
    except module.HistoryBusy as error:
        print(json.dumps({'error': str(error)}), flush=True)
    finally:
        await service.close()
asyncio.run(main())
'''


def test_same_key_workers_merge_after_state_lock_contention(tmp_path, fake_git):
    from app.services.notifications.history import _lock

    async def scenario():
        directory = tmp_path / 'cache'
        service = NotificationHistory(directory)
        held = _lock(state_path_for(service, fake_git, 30))
        processes = []
        try:
            for number in ('1', '2'):
                processes.append(await asyncio.create_subprocess_exec(
                    sys.executable, '-c', STATE_CONTENTION_WORKER,
                    str(directory), str(fake_git), number,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                ))
            # Both independent workers have actually failed to acquire the same
            # lock. They must wait, not turn normal probe contention into a 503.
            await wait_for(lambda: all((fake_git / f'{n}-waiting').exists() for n in ('1', '2')))
            assert events(fake_git) == []
            held.close()
            outputs = await asyncio.wait_for(
                asyncio.gather(*(process.communicate() for process in processes)), 5
            )
            assert all(process.returncode == 0 for process in processes), outputs
            assert [json.loads(stdout) for stdout, _ in outputs] == [
                {'rows': [['abc1234', 'Selected <selected@example.com>']]},
                {'rows': [['abc1234', 'Selected <selected@example.com>']]},
            ]
            assert len(starts(fake_git)) == 1
            for event in events(fake_git):
                if event[0] == 'start':
                    assert_reaped(event[2])
        finally:
            held.close()
            for process in processes:
                if process.returncode is None:
                    process.kill()
                await process.wait()
            await service.close()
    asyncio.run(scenario())
