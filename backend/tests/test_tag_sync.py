"""Tag batches, recovery, concurrent writers and real pushes to temporary remotes."""
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

import pygit2
import pytest
from search.search import Search

from app.db.schemas.user import UserBase
from app.services import sync_dispatch
from app.services.tags import sync, store as storage
from app.services.tags.service import TagService, validate_segments
from app.services.tags.store import TagError, TagStore
from app.services.git.checkout import checkout_lock
from app.services.projects.structure_store import StructureStore
from app.services.publications.store import PublicationStore
from app.services.publications import sync as publication_sync

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app import tasks
    from app.services.git.manager import GitManager
    from app.services.projects import utils as projects

USER = UserBase(github_id=123, username='alice', email='alice@example.org', avatar_url=None, role='administrator')
FIRST = 'tag/pli/ms/sutta/sn1_tag.json'
SECOND = 'tag/pli/ms/sutta/sn2_tag.json'


def write(work, relative, data):
    path = work / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


def read(work, relative):
    return json.loads((work / relative).read_text())


@pytest.fixture
def service(tmp_path):
    work = tmp_path / 'unpublished'
    work.mkdir()
    write(work, '_tags.json', [dict(tag='old', expansion='Old', definition=''),
                              dict(tag='keep', expansion='Keep', definition='')])
    write(work, FIRST, {'sn1:1': 'old, keep', 'sn1:2': 'old'})
    write(work, SECOND, {'sn2:1': 'keep', 'sn2:2': ''})
    return TagService(work)


def rename(service):
    return service.mutate('update', USER, 'old', {'tag': 'renamed'})


@pytest.fixture
def interrupt_tag_rename(monkeypatch):
    """Leave valid redo intent after a passage write succeeds but definitions fail."""
    def interrupt(service):
        original = storage.write_json

        def fail_definition(path, value):
            if path == service.store.work / '_tags.json':
                raise OSError('tag storage unavailable')
            original(path, value)

        monkeypatch.setattr(storage, 'write_json', fail_definition)
        with pytest.raises(OSError, match='tag storage unavailable'):
            rename(service)
        pending = service.store.read_json(service.store.journal)
        assert pending['files']['_tags.json'][0]['tag'] == 'renamed'
        assert read(service.store.work, '_tags.json')[0]['tag'] == 'old'
        assert read(service.store.work, FIRST)['sn1:2'] == 'renamed'
        return pending

    return interrupt


@pytest.mark.parametrize('filename', ['pending.json', 'sync.json'])
def test_invalid_internal_json_is_reported_without_overwrite(service, filename):
    # Invalid bytes are a storage diagnostic, not a simulated atomic-write crash.
    store = service.store
    store.directory.mkdir(parents=True)
    target = store.directory / filename
    target.write_text('{broken')
    with pytest.raises(TagError, match='Invalid JSON'):
        store.recover() if filename == 'pending.json' else store.read_sync()
    assert target.read_text() == '{broken'


def reserve(store, task_id='task'):
    with store.locked():
        state = store.read_sync()
        state.update(status='queued', task_id=task_id)
        store.write_sync(state)
    return state


def test_create_metadata_rename_delete_collect_exact_files(service):
    work = service.store.work
    result = service.mutate('create', USER, data={'tag': 'fresh'})
    assert result['_sync']['status'] == 'pending'
    assert service.store.read_sync()['paths'] == ['_tags.json']
    state = reserve(service.store)
    sync.update_task_state(work, state['generation'], 'task', status='synced')
    service.mutate('update', USER, 'fresh', {'definition': 'Edited'})
    assert service.store.read_sync()['paths'] == ['_tags.json']
    rename(service)
    assert service.store.read_sync()['paths'] == ['_tags.json', FIRST]
    assert read(work, FIRST) == {'sn1:1': 'renamed, keep', 'sn1:2': 'renamed'}
    result = service.mutate('delete', USER, 'renamed')
    assert result['files_modified'] == 1
    assert read(work, FIRST) == {'sn1:1': ' keep', 'sn1:2': ''}
    assert read(work, SECOND) == {'sn2:1': 'keep', 'sn2:2': ''}
    assert (work / FIRST).exists()


def test_noop_does_not_replace_pending_generation(service):
    rename(service)
    state = service.store.read_sync()
    result = service.mutate('update', USER, 'renamed', {'tag': 'renamed', 'expansion': 'Old'})
    assert result['_sync']['generation'] == state['generation']
    assert service.store.read_sync() == state


@pytest.mark.parametrize('broken', ['{broken', '["not an object"]', '{"uid": null}'])
def test_invalid_passage_aborts_before_any_write(service, broken):
    work = service.store.work
    (work / SECOND).write_text(broken)
    before = {p: (work / p).read_bytes() for p in ['_tags.json', FIRST, SECOND]}
    with pytest.raises(TagError):
        rename(service)
    assert before == {p: (work / p).read_bytes() for p in before}
    assert not service.store.journal.exists()


@pytest.mark.parametrize('invalid', ['tag/../../outside_tag.json', 'translation/en/alice/sn1_tag.json'])
def test_save_rejects_invalid_batch_before_journaling_or_writing(service, invalid):
    store = service.store
    original = (store.work / '_tags.json').read_bytes()
    with store.locked():
        with pytest.raises(TagError, match='Invalid path'):
            store.save({'_tags.json': [{'tag': 'new'}], invalid: {'sn1:1': 'new'}},
                       USER.model_dump(), 'Invalid batch')
    assert (store.work / '_tags.json').read_bytes() == original
    assert not store.journal.exists()
    assert not store.sync_path.exists()


@pytest.mark.parametrize('link_kind', ['root', 'directory', 'file'])
def test_rename_rejects_symlinks_without_skipping_references(service, tmp_path, link_kind):
    work = service.store.work
    source = tmp_path / 'linked-data'
    write(source, 'sn3_tag.json', {'sn3:1': 'old'})
    if link_kind == 'root':
        source = tmp_path / 'original-tag'
        (work / 'tag').rename(source)
        link = work / 'tag'
        link.symlink_to(source, target_is_directory=True)
    elif link_kind == 'directory':
        link = work / 'tag/linked'
        link.symlink_to(source, target_is_directory=True)
    else:
        link = work / 'tag/sn3_tag.json'
        link.symlink_to(source / 'sn3_tag.json')
    before = {p: (work / p).read_bytes() for p in ['_tags.json', FIRST, SECOND]}
    linked_before = {p: p.read_bytes() for p in source.rglob('*_tag.json')}
    with pytest.raises(TagError):
        rename(service)
    assert before == {p: (work / p).read_bytes() for p in before}
    assert all(p.read_bytes() == data for p, data in linked_before.items())
    assert link.is_symlink()
    assert not service.store.journal.exists()


def test_recovery_validates_entire_batch_again_before_any_write(service, tmp_path, monkeypatch):
    store = service.store
    files = {'_tags.json': [{'tag': 'new'}], FIRST: {'sn1:1': 'new'}}
    original = (store.work / '_tags.json').read_bytes()
    write_json = storage.write_json

    def interrupted(path, value):
        if path == store.work / '_tags.json':
            raise OSError('interrupted after journal')
        write_json(path, value)

    with monkeypatch.context() as patcher:
        patcher.setattr(storage, 'write_json', interrupted)
        with store.locked():
            with pytest.raises(OSError, match='interrupted after journal'):
                store.save(files, USER.model_dump(), 'Prepared batch')
    journal = store.journal.read_bytes()
    assert json.loads(journal)['files'] == files
    # The next recovery must check the current topology, not reuse old targets.
    target = store.work / FIRST
    prior_passage = target.read_bytes()
    outside = tmp_path / 'outside_tag.json'
    outside.write_bytes(prior_passage)
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(TagError, match='Invalid path'):
        with store.locked():
            pytest.fail('Recovery must reject the changed target')
    assert (store.work / '_tags.json').read_bytes() == original
    assert outside.read_bytes() == prior_passage
    assert target.is_symlink()
    assert store.journal.read_bytes() == journal
    assert not store.sync_path.exists()

    target.unlink()
    target.write_bytes(prior_passage)
    with store.locked():
        assert store.read_tags() == [{'tag': 'new'}]
    assert read(store.work, FIRST) == files[FIRST]
    assert store.read_json(store.journal) is None
    assert store.read_sync()['paths'] == sorted(files)


def test_recovery_finishes_all_files_and_outbox_after_mid_batch_crash(service, monkeypatch, interrupt_tag_rename):
    original = storage.write_json
    interrupt_tag_rename(service)
    assert service.store.read_sync() is None
    with pytest.raises(OSError):
        with service.store.locked():
            pytest.fail('A partial batch must never be exposed by the tag store')
    monkeypatch.setattr(storage, 'write_json', original)
    # Simulate process restart; readers recover the saved intent automatically.
    restarted = TagService(service.store.work)
    assert restarted.list()[0]['tag'] == 'renamed'
    assert restarted.store.read_sync()['paths'] == ['_tags.json', FIRST]
    assert restarted.store.read_sync()['status'] == 'pending'
    assert read(restarted.store.directory, 'pending.json') is None


def test_crash_after_files_before_sync_record_recovers(service, monkeypatch):
    original = storage.write_json

    def failing(path, value):
        if path == service.store.sync_path:
            raise OSError('crash before sync intent')
        original(path, value)

    monkeypatch.setattr(storage, 'write_json', failing)
    with pytest.raises(OSError):
        rename(service)
    monkeypatch.setattr(storage, 'write_json', original)
    assert sync.status(service.store.work)['status'] == 'pending'
    assert service.store.read_sync()['paths'] == ['_tags.json', FIRST]


def test_enqueue_outage_and_expired_delivery_are_recovered(service, monkeypatch):
    rename(service)
    queue = Mock(side_effect=OSError('broker offline'))
    monkeypatch.setattr(tasks.sync_tags, 'apply_async', queue)
    monkeypatch.setattr(sync.time, 'time', lambda: 100)
    sync.dispatch_pending(service.store.work)
    assert sync.status(service.store.work)['status'] == 'pending'
    queue.side_effect = None
    sync.dispatch_pending(service.store.work)
    assert queue.call_count == 1
    monkeypatch.setattr(sync.time, 'time', lambda: 100 + sync_dispatch.DISPATCH_RETRY_DELAY + 1)
    sync.dispatch_pending(service.store.work)
    first_id = sync.status(service.store.work)['task_id']
    assert queue.call_count == 2
    sync.dispatch_pending(service.store.work)
    assert queue.call_count == 2
    monkeypatch.setattr(sync.time, 'time', lambda: 200 + sync.DELIVERY_LEASE)
    sync.dispatch_pending(service.store.work)
    assert queue.call_count == 3
    assert sync.status(service.store.work)['task_id'] != first_id


def test_new_edits_union_pending_paths_and_reject_old_completions(service, monkeypatch):
    rename(service)
    first = reserve(service.store)

    def commit(*args, **kwargs):
        assert kwargs['safe_push'] is True
        service.mutate('delete', USER, 'keep')
        return True

    monkeypatch.setattr(tasks.commit, 'run', commit)
    assert sync.execute_sync(service.store.work, first['generation'], 'task')
    state = service.store.read_sync()
    assert state['paths'] == ['_tags.json', FIRST, SECOND]
    assert state['status'] == 'pending'
    sync.update_task_state(service.store.work, first['generation'], 'task', status='failed')
    assert sync.status(service.store.work)['status'] == 'pending'


def test_retry_and_late_callbacks_keep_terminal_states(service, monkeypatch):
    rename(service)
    first = reserve(service.store)
    monkeypatch.setattr(tasks.settings, 'WORK_DIR', service.store.work)
    task = tasks.TagSyncTask()
    task.on_retry(OSError('network'), 'task', [first['generation']], {}, None)
    assert sync.status(service.store.work)['status'] == 'retrying'
    task.on_failure(OSError('offline'), 'task', [first['generation']], {}, None)
    assert sync.status(service.store.work)['can_retry']
    retry = sync.retry(service.store.work)
    assert retry['generation'] != first['generation']
    sync.update_task_state(service.store.work, first['generation'], 'task', status='synced')
    assert sync.status(service.store.work)['status'] == 'pending'
    state = reserve(service.store, 'new-task')
    sync.update_task_state(service.store.work, state['generation'], 'new-task', status='synced')
    task.on_retry(OSError('late'), 'new-task', [state['generation']], {}, None)
    assert sync.status(service.store.work)['status'] == 'synced'
    with pytest.raises(TagError):
        sync.retry(service.store.work)


def test_superseded_delivery_is_noop(service, monkeypatch):
    rename(service)
    old = reserve(service.store, 'old')
    reserve(service.store, 'new')
    commit = Mock()
    monkeypatch.setattr(tasks.commit, 'run', commit)
    assert sync.execute_sync(service.store.work, old['generation'], 'old') is False
    commit.assert_not_called()


def test_metadata_edit_does_not_drop_failed_reference_paths(service):
    rename(service)
    old = reserve(service.store)
    sync.update_task_state(service.store.work, old['generation'], 'task', status='failed', error='offline')
    service.mutate('update', USER, 'keep', {'definition': 'New'})
    assert service.store.read_sync()['paths'] == ['_tags.json', FIRST]
    assert service.store.read_sync()['status'] == 'pending'


def test_publication_reads_and_saves_ignore_tag_recovery_write_failure(service, interrupt_tag_rename):
    tags = service.store
    pending = interrupt_tag_rename(service)
    publications = PublicationStore(tags.work)
    # Its own interrupted write must still recover, even inside the shared lock.
    write(publications.directory, 'pending.json', {
        '_publication-v2.json': [], '_publication.json': {},
    })
    with checkout_lock(tags.work), publications.locked():
        assert publications.read() == ([], {})
        entry = {'publication_number': 'scpub1'}
        publications.save([entry], {'scpub1': entry}, USER.model_dump())
    with publications.locked():
        assert publications.read() == ([entry], {'scpub1': entry})
    assert publication_sync.status(tags.work, USER)['status'] == 'pending'
    with pytest.raises(OSError, match='tag storage unavailable'):
        sync.status(tags.work)
    assert tags.read_json(tags.journal) == pending


def test_tag_operations_ignore_publication_recovery_write_failure(service, monkeypatch):
    from app.services.publications import store as publication_storage

    publications = PublicationStore(service.store.work)
    original = publication_storage.write_json

    def fail_legacy(path, value):
        if path == publications.work / '_publication.json':
            raise OSError('publication storage unavailable')
        original(path, value)

    monkeypatch.setattr(publication_storage, 'write_json', fail_legacy)
    with pytest.raises(OSError, match='publication storage unavailable'):
        with publications.locked():
            publications.save([], {}, USER.model_dump())
    pending = json.loads(publications.journal.read_text())
    with checkout_lock(service.store.work):
        rename(service)
    assert service.list()[0]['tag'] == 'renamed'
    assert sync.status(service.store.work)['status'] == 'pending'
    assert json.loads(publications.journal.read_text()) == pending
    with pytest.raises(OSError, match='publication storage unavailable'):
        with publications.locked():
            pytest.fail('Publication access must still require its own recovery')


@pytest.mark.parametrize('operation', ['rename', 'delete'])
@pytest.mark.parametrize('relative', [FIRST, '_tags.json'])
def test_pending_structure_cannot_replay_deleted_tag(service, operation, relative):
    structure = StructureStore(service.store.work, service.store.work / 'root/sn1_root-pli-ms.json')
    with checkout_lock(service.store.work), structure.lock():
        structure.prepare({'files': {relative: read(service.store.work, relative)}})
    with pytest.raises(TagError, match='structure operation') as caught:
        rename(service) if operation == 'rename' else service.mutate('delete', USER, 'old')
    assert caught.value.status == 409
    assert service.list()[0]['tag'] == 'old'
    assert read(service.store.work, FIRST)['sn1:2'] == 'old'
    assert service.store.read_sync() is None


def test_concurrent_mutations_serialize_without_lost_definitions(service):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda name: service.mutate('create', USER, data={'tag': name}), ['a', 'b']))
    assert len(results) == 2
    assert {tag['tag'] for tag in service.list()} == {'old', 'keep', 'a', 'b'}


def test_passage_edit_waits_for_rename_then_revalidates(service, monkeypatch):
    work = service.store.work
    root = work / 'root/pli/ms/sutta/sn1_root-pli-ms.json'
    write(work, root.relative_to(work).as_posix(), {'sn1:1': 'A', 'sn1:2': 'B'})
    monkeypatch.setattr(projects.settings, 'WORK_DIR', work)
    monkeypatch.setattr(projects, 'get_user', lambda _: USER)
    writer = Mock()
    monkeypatch.setattr(projects, '_update_file_locked', writer)
    started = Event()

    def edit():
        started.set()
        return projects.update_file(work / FIRST, {'sn1:1': 'old'}, root, USER)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with checkout_lock(work):
            future = pool.submit(edit)
            assert started.wait(2)
            rename(service)
        updated, error, task_id = future.result(timeout=3)
    assert not updated and 'Invalid tags: old' in str(error)
    writer.assert_not_called()


@pytest.mark.parametrize('filename', ['sn1_translation-en-alice.json', 'sn1_tag.json'])
def test_plain_text_save_ignores_tag_recovery_write_failure(service, monkeypatch, interrupt_tag_rename, filename):
    work = service.store.work
    root = work / 'root/pli/ms/sutta/sn1_root-pli-ms.json'
    target = work / 'translation/en/alice/sutta' / filename
    write(work, root.relative_to(work).as_posix(), {'sn1:1': 'A', 'sn1:2': 'B'})
    write(work, target.relative_to(work).as_posix(), {'sn1:1': 'Old', 'sn1:2': 'Kept'})
    pending = interrupt_tag_rename(service)
    monkeypatch.setattr(projects.settings, 'WORK_DIR', work)
    monkeypatch.setattr(projects, 'get_user', lambda _: USER)
    monkeypatch.setattr(projects, 'sort_data', lambda data, _: data)
    monkeypatch.setattr(projects.search, 'update_segments', lambda *_: (True, None))
    enqueue = Mock(return_value='task')
    monkeypatch.setattr(projects, '_schedule_file_commit', enqueue)
    assert projects.update_file(target, {'sn1:1': 'Saved'}, root, USER) == (True, None, 'task')
    assert read(work, target.relative_to(work)) == {'sn1:1': 'Saved', 'sn1:2': 'Kept'}
    enqueue.assert_called_once_with(target, USER)
    # Editing a tag passage must still stop before changing its contents.
    with pytest.raises(OSError, match='tag storage unavailable'):
        projects.update_file(work / FIRST, {'sn1:1': 'keep'}, root, USER)
    assert read(work, FIRST)['sn1:1'] == 'renamed, keep'
    assert service.store.read_json(service.store.journal) == pending


def commit_files(repo, message):
    repo.index.add_all()
    repo.index.write()
    signature = pygit2.Signature('seed', 'seed@example.org')
    return repo.create_commit('HEAD', signature, signature, message, repo.index.write_tree(),
                              [] if repo.head_is_unborn else [repo.head.target])


@pytest.fixture
def git_checkout(service, monkeypatch):
    seed = pygit2.init_repository(str(service.store.work), initial_head='unpublished')
    write(service.store.work, 'unrelated.json', {'original': True})
    commit_files(seed, 'initial')
    remote = pygit2.clone_repository(seed.workdir, str(service.store.work.parent / 'remote.git'), bare=True)
    checkout = pygit2.clone_repository(remote.path, str(service.store.work.parent / 'checkout'))
    other = pygit2.clone_repository(remote.path, str(service.store.work.parent / 'other'))
    work = Path(checkout.workdir)
    monkeypatch.setattr(tasks.settings, 'WORK_DIR', work)
    monkeypatch.setattr(tasks.settings, 'PUBLISHED_DIR', work)
    monkeypatch.setattr(tasks, 'es', Mock())
    with patch('app.services.git.manager.DirectoryIndex') as directory:
        directory.return_value.root = work
        directory.return_value.changes.return_value = nullcontext()
        yield TagService(work), checkout, remote, other


def test_real_push_retries_existing_commit_without_unrelated_staging(git_checkout, monkeypatch):
    service, checkout, remote, other = git_checkout
    work = service.store.work
    write(work, 'unrelated.json', {'staged': True})
    checkout.index.add('unrelated.json')
    checkout.index.write()
    staged_id = checkout.index['unrelated.json'].id
    write(work, 'unrelated.json', {'unstaged': True})
    write(work, 'untracked.json', {'ignore': True})
    rename(service)
    state = reserve(service.store)
    original = GitManager.push
    monkeypatch.setattr(GitManager, 'push', Mock(side_effect=OSError('offline')))
    with pytest.raises(OSError):
        sync.execute_sync(work, state['generation'], 'task')
    committed = checkout.head.target
    assert committed != remote.revparse_single('refs/heads/unpublished').id
    monkeypatch.setattr(GitManager, 'push', original)
    assert sync.execute_sync(work, state['generation'], 'task')
    head = remote.revparse_single('refs/heads/unpublished')
    assert head.id == committed
    assert json.loads(head.tree['_tags.json'].data)[0]['tag'] == 'renamed'
    assert json.loads(head.tree[FIRST].data)['sn1:2'] == 'renamed'
    assert json.loads(head.tree['unrelated.json'].data) == {'original': True}
    assert 'untracked.json' not in head.tree
    assert checkout.index['unrelated.json'].id == staged_id
    assert read(work, 'unrelated.json') == {'unstaged': True}
    assert sync.status(work)['status'] == 'synced'
    assert sync.execute_sync(work, state['generation'], 'task') is False


@pytest.mark.parametrize('task', ['commit', 'pr'])
@pytest.mark.parametrize('own_changes', [False, True])
def test_another_task_commits_tag_batch_separately(git_checkout, monkeypatch, task, own_changes):
    service, checkout, remote, other = git_checkout
    service.mutate('update', USER, 'keep', {'tag': 'kept'})
    state = service.store.read_sync()
    initial = checkout.head.target
    bob = {**USER.model_dump(), 'github_id': 456, 'username': 'bob', 'email': 'bob@example.org'}
    paths = [FIRST]
    if own_changes:
        write(service.store.work, 'unrelated.json', {'bob': True})
        paths.append('unrelated.json')
    write(service.store.work, 'staged.json', {'exclude': True})
    checkout.index.add('staged.json')
    checkout.index.write()
    staged_id = checkout.index['staged.json'].id
    publish = Mock(return_value='fixture-pr')
    monkeypatch.setattr(GitManager, 'publish_files', publish)
    push = Mock(wraps=GitManager.push)
    monkeypatch.setattr(GitManager, 'push', push)
    if task == 'commit':
        assert tasks.commit.run(bob, paths, 'Bob passage edit')
    else:
        assert tasks.pr.run(bob, paths) == 'fixture-pr'
        publish.assert_called_once_with([Path(path) for path in paths])
    head = remote.revparse_single('refs/heads/unpublished')
    batch = head.parents[0] if own_changes else head
    assert batch.parents[0].id == initial
    assert batch.author.name == USER.username
    assert batch.author.email == USER.email
    assert batch.message == state['message']
    assert GitManager.get_changed_paths(checkout, str(initial), str(batch.id)) == {
        Path('_tags.json'), Path(FIRST), Path(SECOND)}
    if own_changes:
        assert head.author.name == 'bob'
        assert head.author.email == 'bob@example.org'
        assert head.message == ('Bob passage edit' if task == 'commit' else 'Translations by bob')
        assert GitManager.get_changed_paths(checkout, str(batch.id), str(head.id)) == {Path('unrelated.json')}
    assert json.loads(head.tree[FIRST].data)['sn1:1'] == 'old, kept'
    assert json.loads(head.tree[SECOND].data)['sn2:1'] == 'kept'
    assert 'staged.json' not in head.tree
    assert checkout.index['staged.json'].id == staged_id
    push.assert_called_once()
    assert push.call_args.args[0].workdir == checkout.workdir
    assert push.call_args.args[1:] == ('origin', 'unpublished')
    assert push.call_args.kwargs == {'force': False}
    assert service.store.read_sync() == state
    # Only the dedicated sync delivery confirms success; it must not create a
    # duplicate commit or reassign the already recorded authors.
    state = reserve(service.store)
    assert sync.execute_sync(service.store.work, state['generation'], 'task')
    assert remote.revparse_single('refs/heads/unpublished').id == head.id
    assert sync.status(service.store.work)['status'] == 'synced'


@pytest.mark.parametrize('task', ['commit', 'pr'])
@pytest.mark.parametrize('own_changes', [False, True])
def test_separate_tag_commit_push_retry_keeps_history(git_checkout, monkeypatch, task, own_changes):
    service, checkout, remote, other = git_checkout
    rename(service)
    state = service.store.read_sync()
    initial = checkout.head.target
    bob = {**USER.model_dump(), 'username': 'bob', 'email': 'bob@example.org'}
    paths = [FIRST]
    if own_changes:
        write(service.store.work, 'unrelated.json', {'bob': True})
        paths.append('unrelated.json')
    publish = Mock(return_value='fixture-pr')
    monkeypatch.setattr(GitManager, 'publish_files', publish)
    original_push = GitManager.push
    monkeypatch.setattr(GitManager, 'push', Mock(side_effect=OSError('offline')))
    args = (bob, paths, 'Bob edit') if task == 'commit' else (bob, paths)
    with pytest.raises(OSError, match='offline'):
        getattr(tasks, task).run(*args)
    committed = checkout.head.target
    assert committed != initial
    assert remote.revparse_single('refs/heads/unpublished').id == initial
    assert service.store.read_sync() == state
    publish.assert_not_called()
    monkeypatch.setattr(GitManager, 'push', original_push)
    assert getattr(tasks, task).run(*args)
    assert checkout.head.target == committed
    assert remote.revparse_single('refs/heads/unpublished').id == committed
    assert service.store.read_sync() == state
    if task == 'pr':
        publish.assert_called_once_with([Path(path) for path in paths])


@pytest.mark.parametrize('task', ['commit', 'pr'])
def test_failed_tag_batch_commit_stops_current_task(git_checkout, monkeypatch, task):
    service, checkout, remote, other = git_checkout
    rename(service)
    state = service.store.read_sync()
    initial = checkout.head.target
    commit = Mock(side_effect=OSError('tag commit unavailable'))
    pull = Mock()
    push = Mock()
    publish = Mock()
    monkeypatch.setattr(GitManager, 'commit', commit)
    monkeypatch.setattr(GitManager, 'pull', pull)
    monkeypatch.setattr(GitManager, 'push', push)
    monkeypatch.setattr(GitManager, 'publish_files', publish)
    args = (USER.model_dump(), [FIRST], 'Passage edit') if task == 'commit' else (USER.model_dump(), [FIRST])
    with pytest.raises(OSError, match='tag commit unavailable'):
        getattr(tasks, task).run(*args)
    commit.assert_called_once()
    assert commit.call_args.args[3] == state['message']
    assert checkout.head.target == initial
    assert remote.revparse_single('refs/heads/unpublished').id == initial
    assert service.store.read_sync() == state
    pull.assert_not_called()
    push.assert_not_called()
    publish.assert_not_called()


@pytest.mark.parametrize('task', ['commit', 'pr'])
def test_nonoverlapping_tag_commit_leaves_batch_pending(git_checkout, monkeypatch, task):
    service, checkout, remote, other = git_checkout
    rename(service)  # Only FIRST and _tags.json belong to this batch.
    state = service.store.read_sync()
    initial = checkout.head.target
    write(service.store.work, SECOND, {'sn2:1': '', 'sn2:2': 'keep'})
    monkeypatch.setattr(GitManager, 'publish_files', Mock(return_value='fixture-pr'))
    bob = {**USER.model_dump(), 'username': 'bob', 'email': 'bob@example.org'}
    args = (bob, [SECOND], 'Bob edit') if task == 'commit' else (bob, [SECOND])
    assert getattr(tasks, task).run(*args)
    head = remote.revparse_single('refs/heads/unpublished')
    assert head.parents[0].id == initial
    assert head.author.name == 'bob'
    assert GitManager.get_changed_paths(checkout, str(initial), str(head.id)) == {Path(SECOND)}
    assert json.loads(head.tree['_tags.json'].data)[0]['tag'] == 'old'
    assert service.store.read_sync() == state


def test_remote_conflict_preserves_local_and_remote(git_checkout):
    service, checkout, remote, other = git_checkout
    rename(service)
    state = reserve(service.store)
    write(Path(other.workdir), '_tags.json', [{'tag': 'different'}])
    remote_commit = commit_files(other, 'remote tags')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    with pytest.raises(ValueError, match='conflicts with origin/unpublished'):
        sync.execute_sync(service.store.work, state['generation'], 'task')
    assert remote.revparse_single('refs/heads/unpublished').id == remote_commit
    assert checkout.index.conflicts is None
    assert service.list()[0]['tag'] == 'renamed'
    assert sync.status(service.store.work)['status'] != 'synced'


def test_remote_merge_keeps_unrelated_staged_file_out_of_merge(git_checkout):
    service, checkout, remote, other = git_checkout
    rename(service)
    state = reserve(service.store)
    write(service.store.work, 'unrelated.json', {'staged': True})
    checkout.index.add('unrelated.json')
    checkout.index.write()
    staged_id = checkout.index['unrelated.json'].id
    write(Path(other.workdir), 'remote.json', {'remote': True})
    remote_commit = commit_files(other, 'remote addition')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    assert sync.execute_sync(service.store.work, state['generation'], 'task')
    head = remote.revparse_single('refs/heads/unpublished')
    assert remote.descendant_of(head.id, remote_commit)
    assert json.loads(head.tree['unrelated.json'].data) == {'original': True}
    assert checkout.index['unrelated.json'].id == staged_id


def test_tag_sync_indexes_remote_translation_changes_and_deletions(git_checkout):
    service, checkout, remote, other = git_checkout
    work = service.store.work
    remote_work = Path(other.workdir)
    added = 'translation/en/alice/sutta/sn3_translation-en-alice.json'
    modified = 'translation/en/alice/sutta/sn1_translation-en-alice.json'
    deleted = 'translation/en/alice/sutta/sn2_translation-en-alice.json'
    write(remote_work, modified, {'sn1:1': 'Original translation'})
    write(remote_work, deleted, {'sn2:1': 'Translation to remove'})
    commit_files(other, 'initial translations')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    GitManager(work, work, USER).pull(checkout)

    rename(service)
    state = reserve(service.store)
    write(remote_work, added, {'sn3:1': 'New remote translation'})
    write(remote_work, modified, {'sn1:1': 'Updated remote translation'})
    (remote_work / deleted).unlink()
    commit_files(other, 'remote translation changes')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])

    assert sync.execute_sync(work, state['generation'], 'task')
    assert read(work, added) == {'sn3:1': 'New remote translation'}
    assert read(work, modified) == {'sn1:1': 'Updated remote translation'}
    assert not (work / deleted).exists()
    calls = tasks.es.update_indexes.call_args_list
    indexed = {path for call in calls if not call.kwargs.get('delete') for path in call.args[2]}
    removed = {path for call in calls if call.kwargs.get('delete') for path in call.args[2]}
    assert {work / added, work / modified} <= indexed
    assert work / deleted not in indexed
    assert removed == {work / deleted}
    for call in calls:
        assert call.args[:2] == (tasks.settings.ES_INDEX, tasks.settings.ES_SEGMENTS_INDEX)
    assert sync.status(work)['status'] == 'synced'


@pytest.mark.parametrize('operation,data', [('create', {'tag': 'fresh'}),
                                           ('update', {'definition': 'Edited'}),
                                           ('delete', None)])
def test_all_mutations_reach_remote(git_checkout, operation, data):
    service, checkout, remote, other = git_checkout
    result = service.mutate(operation, USER, 'old', data)
    state = reserve(service.store)
    assert sync.execute_sync(service.store.work, state['generation'], 'task')
    head = remote.revparse_single('refs/heads/unpublished')
    definitions = json.loads(head.tree['_tags.json'].data)
    assert definitions == service.list()
    if operation == 'delete':
        assert json.loads(head.tree[FIRST].data)['sn1:2'] == ''
    else:
        assert json.loads(head.tree[FIRST].data)['sn1:2'] == 'old'
    assert sync.status(service.store.work)['status'] == 'synced'


def test_rename_without_passage_directory(service):
    import shutil
    shutil.rmtree(service.store.work / 'tag')
    rename(service)
    assert service.store.read_sync()['paths'] == ['_tags.json']


def test_new_edits_during_push_remain_pending_and_then_sync(git_checkout, monkeypatch):
    service, checkout, remote, other = git_checkout
    rename(service)
    first = reserve(service.store)
    original = GitManager.push

    def push(*args, **kwargs):
        # A different writer can save during network I/O, after the first local commit.
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(service.mutate, 'delete', USER, 'keep').result(timeout=3)
        return original(*args, **kwargs)

    monkeypatch.setattr(GitManager, 'push', push)
    assert sync.execute_sync(service.store.work, first['generation'], 'task')
    assert service.store.read_sync()['status'] == 'pending'
    assert service.store.read_sync()['paths'] == ['_tags.json', FIRST, SECOND]
    monkeypatch.setattr(GitManager, 'push', original)
    second = reserve(service.store, 'second')
    assert sync.execute_sync(service.store.work, second['generation'], 'second')
    head = remote.revparse_single('refs/heads/unpublished')
    assert json.loads(head.tree[SECOND].data)['sn2:1'] == ''
    assert json.loads(head.tree['_tags.json'].data) == service.list()


def test_unrelated_staged_deletion_is_preserved(git_checkout):
    service, checkout, remote, other = git_checkout
    (service.store.work / 'unrelated.json').unlink()
    checkout.index.remove('unrelated.json')
    checkout.index.write()
    rename(service)
    state = reserve(service.store)
    assert sync.execute_sync(service.store.work, state['generation'], 'task')
    assert 'unrelated.json' in remote.revparse_single('refs/heads/unpublished').tree
    with pytest.raises(KeyError):
        checkout.index['unrelated.json']
    assert not (service.store.work / 'unrelated.json').exists()


@pytest.mark.parametrize('task', ['commit', 'pr'])
@pytest.mark.parametrize('path', ['unrelated.json', '_publication-v2.json'])
def test_non_tag_tasks_do_not_read_tag_sync_state(git_checkout, monkeypatch, task, path):
    service, checkout, remote, other = git_checkout
    tags = service.store
    # Only overlapping tag batch commits need sync state; pull needs redo recovery.
    sync_read = Mock(side_effect=AssertionError('unrelated operation read tag sync state'))
    monkeypatch.setattr(TagStore, 'read_sync', sync_read)
    write(tags.work, path, {'updated': True})
    publish = Mock(return_value='fixture-pr')
    monkeypatch.setattr(GitManager, 'publish_files', publish)
    if task == 'commit':
        assert tasks.commit.run(USER.model_dump(), [path], 'Independent edit')
    else:
        assert tasks.pr.run(USER.model_dump(), [path]) == 'fixture-pr'
        publish.assert_called_once_with([Path(path)])
    head = remote.revparse_single('refs/heads/unpublished')
    assert json.loads(head.tree[path].data) == {'updated': True}
    sync_read.assert_not_called()


@pytest.mark.parametrize('task', ['commit', 'pr'])
def test_non_tag_local_commit_precedes_checkout_wide_recovery(git_checkout, task, interrupt_tag_rename):
    service, checkout, remote, other = git_checkout
    tags = service.store
    pending = interrupt_tag_rename(service)
    initial = checkout.head.target
    write(tags.work, 'unrelated.json', {'updated': True})
    with pytest.raises(OSError, match='tag storage unavailable'):
        if task == 'commit':
            tasks.commit.run(USER.model_dump(), ['unrelated.json'], 'Independent edit')
        else:
            tasks.pr.run(USER.model_dump(), ['unrelated.json'])
    # Local staging/commit is independent; whole-checkout pull still requires
    # healthy recovery before it may overwrite any files. Nothing is pushed.
    assert checkout.head.target != initial
    assert json.loads(checkout.head.peel().tree['unrelated.json'].data) == {'updated': True}
    assert remote.revparse_single('refs/heads/unpublished').id == initial
    assert tags.read_json(tags.journal) == pending


@pytest.mark.parametrize('force', [False, True])
def test_pull_waits_for_tag_batch_recovery_before_updating_checkout(git_checkout, force, interrupt_tag_rename):
    service, checkout, remote, other = git_checkout
    work = service.store.work
    write(Path(other.workdir), 'unrelated.json', {'remote': True})
    commit_files(other, 'remote edit')
    other.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished'])
    pending = interrupt_tag_rename(service)
    initial = checkout.head.target
    index = (Path(checkout.path) / 'index').read_bytes()
    manager = GitManager(work, work, USER)
    with pytest.raises(OSError, match='tag storage unavailable'):
        manager.pull(checkout, force=force)
    assert checkout.head.target == initial
    assert (Path(checkout.path) / 'index').read_bytes() == index
    assert read(work, 'unrelated.json') == {'original': True}
    assert service.store.read_json(service.store.journal) == pending
