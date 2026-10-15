"""Publication outbox recovery and Git synchronization, using only temporary files/remotes."""
import asyncio
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pygit2
import pytest
from search.search import Search

from app.services.publications import sync
from app.services.publications import store as storage

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app import tasks
    from app.services.git.manager import GitManager

USER = dict(github_id=123, username='alice', email='alice@example.org', avatar_url=None, role='writer')


@pytest.fixture
def store(tmp_path):
    work = tmp_path / 'unpublished'
    work.mkdir()
    return storage.PublicationStore(work)


def save(store, title='Saved'):
    with store.locked():
        return store.save([{'publication_number': 'scpub1', 'translation_title': title}],
                          {'scpub1': {'publication_number': 'scpub1', 'translation_title': title}}, USER)


def reserve(store, task_id='task'):
    with store.locked():
        state = store.read_sync()
        state.update(status='queued', task_id=task_id)
        store.write_sync(state)
    return state


def test_crash_after_metadata_write_recovers_sync_intent(store, monkeypatch):
    original = store.write_sync
    monkeypatch.setattr(store, 'write_sync', Mock(side_effect=OSError('crash')))
    with pytest.raises(OSError):
        save(store)
    assert json.loads(store.journal.read_text())['sync']['status'] == 'pending'
    monkeypatch.setattr(store, 'write_sync', original)
    # A new instance models a restarted process.
    recovered = storage.PublicationStore(store.work)
    with recovered.locked():
        assert recovered.read_sync()['status'] == 'pending'
        assert recovered.read()[0][0]['translation_title'] == 'Saved'
        assert json.loads(recovered.journal.read_text()) is None


def test_recovery_dispatch_and_delivery_lease(store, monkeypatch):
    state = save(store)
    queue = Mock()
    monkeypatch.setattr(tasks.sync_publications, 'apply_async', queue)
    monkeypatch.setattr(sync.time, 'time', lambda: 100)
    sync.dispatch_pending(store.work)
    sync.dispatch_pending(store.work)
    queue.assert_called_once()
    assert queue.call_args.kwargs['args'] == [state['generation']]
    first_id = queue.call_args.kwargs['task_id']
    monkeypatch.setattr(sync.time, 'time', lambda: 100 + sync.DELIVERY_LEASE + 1)
    sync.dispatch_pending(store.work)
    assert queue.call_count == 2
    assert queue.call_args.kwargs['task_id'] != first_id


def test_old_completion_and_failure_cannot_overwrite_new_save(store, monkeypatch):
    save(store)
    previous = reserve(store)
    saved = []

    def commit(*args, **kwargs):
        assert kwargs['safe_push'] is True
        saved.append(save(store, 'Newer'))
        return True

    monkeypatch.setattr(tasks.commit, 'run', commit)
    assert sync.execute_sync(store.work, previous['generation'], 'task')
    with store.locked():
        assert store.read_sync()['generation'] == saved[0]['generation']
        assert store.read_sync()['status'] == 'pending'
    sync.update_task_state(store.work, previous['generation'], 'task', status='failed', error='old failure')
    assert sync.status(store.work, SimpleNamespace(**USER))['status'] == 'pending'


def test_superseded_delivery_does_not_commit_or_change_status(store, monkeypatch):
    save(store)
    previous = reserve(store, 'old')
    reserve(store, 'new')
    commit = Mock()
    monkeypatch.setattr(tasks.commit, 'run', commit)
    assert sync.execute_sync(store.work, previous['generation'], 'old') is False
    sync.update_task_state(store.work, previous['generation'], 'old', status='failed')
    commit.assert_not_called()
    assert sync.status(store.work, SimpleNamespace(**USER))['task_id'] == 'new'


def test_task_retry_and_failure_are_durable(store, monkeypatch):
    save(store)
    state = reserve(store)
    monkeypatch.setattr(tasks.settings, 'WORK_DIR', store.work)
    task = tasks.PublicationSyncTask()
    task.on_retry(OSError('offline'), 'task', [state['generation']], {}, None)
    assert sync.status(store.work, SimpleNamespace(**USER))['status'] == 'retrying'
    task.on_failure(OSError('still offline'), 'task', [state['generation']], {}, None)
    status = sync.status(store.work, SimpleNamespace(**USER))
    assert status['status'] == 'failed'
    assert status['can_retry']
    assert sync.retry(store.work, SimpleNamespace(**USER))['status'] == 'pending'


@pytest.mark.asyncio
async def test_background_loop_dispatches_on_start_without_a_browser(store, monkeypatch):
    save(store)
    queue = Mock()
    monkeypatch.setattr(tasks.sync_publications, 'apply_async', queue)

    async def stop(delay):
        assert delay == sync.DISPATCH_INTERVAL
        raise asyncio.CancelledError

    monkeypatch.setattr(sync.asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError):
        await sync.dispatch_loop(store.work)
    queue.assert_called_once()


def commit_files(repo, message):
    repo.index.add_all()
    repo.index.write()
    signature = pygit2.Signature('Tester', 'test@example.org')
    parents = [] if repo.head_is_unborn else [repo.head.target]
    return repo.create_commit('HEAD', signature, signature, message, repo.index.write_tree(), parents)


@pytest.fixture
def git_checkout(tmp_path, monkeypatch):
    seed = pygit2.init_repository(str(tmp_path / 'seed'), initial_head='unpublished')
    seed_store = storage.PublicationStore(Path(seed.workdir))
    save(seed_store, 'Original')
    commit_files(seed, 'initial')
    remote = pygit2.clone_repository(seed.workdir, str(tmp_path / 'remote.git'), bare=True)
    checkout = pygit2.clone_repository(remote.path, str(tmp_path / 'checkout'))
    other = pygit2.clone_repository(remote.path, str(tmp_path / 'other'))
    monkeypatch.setattr(tasks.settings, 'WORK_DIR', Path(checkout.workdir))
    monkeypatch.setattr(tasks.settings, 'PUBLISHED_DIR', Path(checkout.workdir))
    monkeypatch.setattr(tasks, 'es', Mock())
    with patch('app.services.git.manager.DirectoryIndex') as directory:
        directory.return_value.root = Path(checkout.workdir)
        directory.return_value.changes.return_value = nullcontext()
        yield checkout, remote, other


def test_real_git_sync_pushes_both_files_and_retries_committed_content(git_checkout, monkeypatch):
    checkout, remote, other = git_checkout
    store = storage.PublicationStore(Path(checkout.workdir))
    save(store, 'Automatic')
    state = reserve(store)
    original_push = GitManager.push
    monkeypatch.setattr(GitManager, 'push', Mock(side_effect=OSError('connection interrupted')))
    with pytest.raises(OSError, match='connection interrupted'):
        sync.execute_sync(store.work, state['generation'], 'task')
    committed = checkout.head.target
    assert committed != remote.revparse_single('refs/heads/unpublished').id
    assert sync.status(store.work, SimpleNamespace(**USER))['status'] != 'synced'
    monkeypatch.setattr(GitManager, 'push', original_push)
    assert sync.execute_sync(store.work, state['generation'], 'task')
    assert checkout.head.target == committed
    assert sync.status(store.work, SimpleNamespace(**USER))['status'] == 'synced'
    head = remote.revparse_single('refs/heads/unpublished')
    assert json.loads(head.tree[storage.PUBLICATION_FILES[0]].data)[0]['translation_title'] == 'Automatic'
    assert json.loads(head.tree[storage.PUBLICATION_FILES[1]].data)['scpub1']['translation_title'] == 'Automatic'
    # No new file diff: a redelivery must still successfully push an existing commit.
    reserve(store)
    assert sync.execute_sync(store.work, state['generation'], 'task')
    assert remote.revparse_single('refs/heads/unpublished').id == head.id


def test_remote_conflict_leaves_local_files_intact(git_checkout):
    checkout, remote, other = git_checkout
    store = storage.PublicationStore(Path(checkout.workdir))
    save(store, 'Local edit')
    state = reserve(store)
    save(storage.PublicationStore(Path(other.workdir)), 'Remote edit')
    remote_commit = commit_files(other, 'remote edit')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    with pytest.raises(ValueError, match='conflicts with origin/unpublished'):
        sync.execute_sync(store.work, state['generation'], 'task')
    assert store.read_v2()[0]['translation_title'] == 'Local edit'
    assert checkout.index.conflicts is None
    assert remote.revparse_single('refs/heads/unpublished').id == remote_commit


def test_non_force_push_rejects_remote_advance(git_checkout):
    checkout, remote, other = git_checkout
    (Path(checkout.workdir) / 'local.txt').write_text('local')
    commit_files(checkout, 'local commit')
    (Path(other.workdir) / 'remote.txt').write_text('remote')
    remote_commit = commit_files(other, 'remote commit')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    with pytest.raises(pygit2.GitError):
        GitManager.push(checkout, force=False)
    assert remote.revparse_single('refs/heads/unpublished').id == remote_commit


def test_server_rejection_callback_is_an_error():
    repo = Mock()
    remote = Mock()
    repo.remotes = {'origin': remote}
    GitManager.push(repo, force=False)
    args = remote.push.call_args
    assert args.args[0] == ['refs/heads/unpublished:refs/heads/unpublished']
    with pytest.raises(pygit2.GitError, match='branch protected'):
        args.kwargs['callbacks'].push_update_reference('refs/heads/unpublished', 'branch protected')


def test_completed_sync_cannot_be_regressed_by_a_late_callback(store):
    save(store)
    state = reserve(store)
    sync.update_task_state(store.work, state['generation'], 'task', status='synced')
    sync.update_task_state(store.work, state['generation'], 'task', status='retrying', error='late error')
    assert sync.status(store.work, SimpleNamespace(**USER))['status'] == 'synced'


def test_nonconflicting_remote_edit_is_merged_before_publication_push(git_checkout):
    checkout, remote, other = git_checkout
    store = storage.PublicationStore(Path(checkout.workdir))
    save(store, 'Local edit')
    state = reserve(store)
    (Path(other.workdir) / 'remote.txt').write_text('remote addition')
    remote_commit = commit_files(other, 'remote addition')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    assert sync.execute_sync(store.work, state['generation'], 'task')
    head = remote.revparse_single('refs/heads/unpublished')
    assert head.tree['remote.txt'].data == b'remote addition'
    assert json.loads(head.tree[storage.PUBLICATION_FILES[0]].data)[0]['translation_title'] == 'Local edit'
    assert remote.descendant_of(head.id, remote_commit)
