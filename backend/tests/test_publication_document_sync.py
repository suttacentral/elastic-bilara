"""Durable saves and Git publication against temporary local bare remotes only."""
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from github import GithubException
from kombu.exceptions import OperationalError
import pygit2
import pytest
from search.search import Search

from app.services.publication_documents import requests as document_requests, sync
from app.services.publication_documents.catalog import document_id
from app.services.publication_documents.service import DocumentService
from app.services.publication_documents.store import DocumentStore, read_html, revision
from app.services.publications.errors import PublicationError

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app import tasks
    from app.services.git.manager import GitManager

PATH = '_publication/en/alice/editions/dn/matter/introduction.html'
OTHER = '_publication/en/alice/editions/dn/matter/preface.html'
ORIGINAL = '<article><h1 id="intro">Introduction</h1><p>Original</p></article>\n'
EDITED = ORIGINAL.replace('Original', 'Edited')
USER = dict(github_id=123, username='alice', email='alice@example.org', avatar_url=None, role='writer')


def commit_all(repo):
    repo.index.add_all(); repo.index.write()
    sig = pygit2.Signature('Fixture', 'fixture@example.org')
    return repo.create_commit('HEAD', sig, sig, 'fixture', repo.index.write_tree(), [] if repo.head_is_unborn else [repo.head.target])


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    seed = pygit2.init_repository(str(tmp_path / 'seed'), initial_head='unpublished')
    root = Path(seed.workdir)
    for path in (PATH, OTHER):
        file = root / path; file.parent.mkdir(parents=True, exist_ok=True); file.write_text(ORIGINAL)
    (root / '_publication-v2.json').write_text(json.dumps([{'publication_number': 'scpub1', 'creator_github_handle': 'alice'}]))
    (root / '_publication/en/alice/editions/dn/web.json').write_text(json.dumps({
        'publication_number': 'scpub1', 'edition_number': 'ed1', 'publication_type': 'web',
        'frontmatter': ['./matter/introduction.html', './matter/preface.html']}))
    (root / 'unrelated.txt').write_text('untouched')
    initial = commit_all(seed)
    seed.create_branch('published', seed[initial])
    remote = pygit2.clone_repository(seed.workdir, str(tmp_path / 'remote.git'), bare=True)
    remote.references.create('refs/heads/published', initial)
    work = pygit2.clone_repository(remote.path, str(tmp_path / 'unpublished'), checkout_branch='unpublished')
    published = pygit2.clone_repository(remote.path, str(tmp_path / 'published'), checkout_branch='published')
    other = pygit2.clone_repository(remote.path, str(tmp_path / 'other'), checkout_branch='published')
    user = SimpleNamespace(**USER, is_active=True)
    user.model_dump = lambda: USER.copy()
    monkeypatch.setattr('app.services.users.utils.get_user', lambda _: user)
    monkeypatch.setattr(tasks.settings, 'WORK_DIR', Path(work.workdir))
    monkeypatch.setattr(tasks.settings, 'PUBLISHED_DIR', Path(published.workdir))
    monkeypatch.setattr(tasks, 'es', Mock())
    prs = Mock()
    prs.list_open.return_value = {}
    prs.get.return_value = SimpleNamespace(state='open', merged=False)
    prs.create.return_value = SimpleNamespace(number=1, html_url='https://example.test/pull/1')
    monkeypatch.setattr('app.services.git.manager.GithubPullRequests', lambda *args: prs)
    monkeypatch.setattr('app.services.publication_documents.requests.GithubPullRequests', lambda *args: prs)
    with patch('app.services.git.manager.DirectoryIndex') as directory:
        directory.return_value.root = Path(work.workdir)
        directory.return_value.changes.return_value = nullcontext()
        yield SimpleNamespace(work=work, published=published, remote=remote, other=other, prs=prs, user=user,
            service=DocumentService(Path(work.workdir), Path(published.workdir), user), uid=document_id(PATH))


def save(checkout, content=EDITED):
    before = checkout.service.get('scpub1', checkout.uid)
    return checkout.service.save('scpub1', checkout.uid, SimpleNamespace(content=content,
        revision=before['revision'], published_revision=before['published_revision']))


def reserve(checkout, operation='sync', task_id='task'):
    store = DocumentStore(checkout.work.workdir, 'scpub1', operation)
    with store.locked():
        job = store.read_sync()
        job.update(status='queued', task_id=task_id)
        store.write_sync(job)
    return job


def run(checkout, job, operation='sync', task_id='task'):
    return sync.execute(Path(checkout.work.workdir), Path(checkout.published.workdir), job['generation'], task_id, 'scpub1', operation)


def request_release(checkout):
    detail = checkout.service.get('scpub1', checkout.uid)
    checkout.service.publish('scpub1', [SimpleNamespace(id=checkout.uid, revision=detail['revision'], published_revision=detail['published_revision'])])
    return reserve(checkout, 'publish')


def test_save_recovery_keeps_html_and_sync_intent_together(checkout, monkeypatch):
    original = DocumentStore.write
    monkeypatch.setattr(DocumentStore, 'write', Mock(side_effect=OSError('disk interrupted')))
    with pytest.raises(OSError):
        save(checkout)
    store = DocumentStore(checkout.work.workdir, 'scpub1')
    assert json.loads(store.journal.read_text())['content'] == EDITED
    monkeypatch.setattr(DocumentStore, 'write', original)
    with store.locked():
        assert store.read_sync()['documents'][checkout.uid]['revision'] == revision(EDITED)
        assert json.loads(store.journal.read_text()) is None
    assert read_html(Path(checkout.work.workdir) / PATH) == EDITED


def test_dispatch_reserves_once_and_recovers_broker_failure(checkout, monkeypatch):
    save(checkout)
    queue = Mock(side_effect=OperationalError('offline'))
    monkeypatch.setattr(tasks.process_publication_documents, 'apply_async', queue)
    sync.dispatch_safely(Path(checkout.work.workdir), 'scpub1')
    state = DocumentStore(checkout.work.workdir, 'scpub1').read_sync()
    assert state['status'] == 'pending'
    assert 'offline' in state['error']
    assert state['dispatch_after'] > 0


def test_sync_pushes_only_selected_files_and_preserves_unrelated_staging(checkout):
    save(checkout)
    unrelated = Path(checkout.work.workdir) / 'unrelated.txt'
    unrelated.write_text('staged by someone else')
    checkout.work.index.add('unrelated.txt'); checkout.work.index.write()
    staged = checkout.work.index['unrelated.txt'].id
    assert run(checkout, reserve(checkout))
    remote_head = checkout.remote.lookup_reference('refs/heads/unpublished').peel(pygit2.Commit)
    assert remote_head.tree[PATH].data.decode() == EDITED
    assert remote_head.tree[OTHER].data.decode() == ORIGINAL
    assert remote_head.tree['unrelated.txt'].data == b'untouched'
    assert checkout.work.index['unrelated.txt'].id == staged
    assert checkout.service.status('scpub1')['sync']['status'] == 'synced'


def test_failed_push_retries_the_existing_commit(checkout, monkeypatch):
    save(checkout)
    job = reserve(checkout)
    push = GitManager.push
    monkeypatch.setattr(GitManager, 'push', Mock(side_effect=OSError('connection interrupted')))
    with pytest.raises(OSError):
        run(checkout, job)
    committed = checkout.work.head.target
    monkeypatch.setattr(GitManager, 'push', push)
    assert run(checkout, job)
    assert checkout.work.head.target == committed
    assert checkout.remote.lookup_reference('refs/heads/unpublished').target == committed


def test_new_generation_cannot_be_cleared_by_old_task(checkout):
    save(checkout)
    old = reserve(checkout)
    save(checkout, EDITED.replace('Edited', 'Latest'))
    sync.update_task_state(checkout.work.workdir, old['generation'], 'task', 'scpub1', 'sync', status='failed')
    assert not run(checkout, old)
    assert checkout.service.status('scpub1')['sync']['status'] == 'pending'


@pytest.mark.parametrize('failure', [None, 'push', 'pr-create'])
def test_publish_cleans_local_branch_without_touching_published_checkout(checkout, monkeypatch, failure):
    save(checkout)
    job = request_release(checkout)
    branch = 'publication-documents-scpub1-' + job['generation']
    local_ref = 'refs/heads/' + branch
    before_head = checkout.published.head.target
    path = Path(checkout.published.workdir) / OTHER
    path.write_text('uncommitted published work')
    checkout.published.index.add(OTHER); checkout.published.index.write()
    before_index = checkout.published.index[OTHER].id
    if failure:
        original_push = GitManager.push

        def interrupted_push(repo, *args, **kwargs):
            if repo.path == checkout.published.path:
                assert local_ref in repo.references
                raise OSError('Push interrupted')
            return original_push(repo, *args, **kwargs)

        with monkeypatch.context() as patcher:
            if failure == 'push':
                patcher.setattr(GitManager, 'push', staticmethod(interrupted_push))
            else:
                patcher.setattr(checkout.prs.create, 'side_effect', OSError('PR creation interrupted'))
            with pytest.raises(OSError, match='interrupted'):
                run(checkout, job, 'publish')
        assert local_ref not in checkout.published.references
        assert checkout.published.head.target == before_head
        assert checkout.published.index[OTHER].id == before_index
        assert path.read_text() == 'uncommitted published work'
    # Failed publication attempts remain retryable after local-ref cleanup.
    assert run(checkout, job, 'publish')
    assert local_ref not in checkout.published.references
    pr_head = checkout.remote.lookup_reference('refs/heads/' + branch).peel(pygit2.Commit)
    assert pr_head.tree[PATH].data.decode() == EDITED
    assert pr_head.tree[OTHER].data.decode() == ORIGINAL
    assert checkout.remote.lookup_reference('refs/heads/published').target == before_head
    assert checkout.published.head.target == before_head
    assert checkout.published.index[OTHER].id == before_index
    assert path.read_text() == 'uncommitted published work'
    assert checkout.service.status('scpub1')['publish']['url'] == 'https://example.test/pull/1'


def test_publish_prunes_deleted_remote_tracking_refs_but_keeps_other_local_branches(checkout):
    save(checkout)
    job = request_release(checkout)
    local_ref = 'refs/heads/previous-publication'
    remote_ref = 'refs/remotes/origin/previous-publication'
    target = checkout.published.head.target
    checkout.remote.references.create(local_ref, target)
    checkout.published.remotes['origin'].fetch()
    checkout.published.references.create(local_ref, target)
    checkout.remote.lookup_reference(local_ref).delete()
    assert remote_ref in checkout.published.references
    assert run(checkout, job, 'publish')
    assert remote_ref not in checkout.published.references
    assert checkout.published.lookup_reference(local_ref).target == target


def test_published_remote_change_blocks_release_even_when_local_baseline_is_stale(checkout):
    save(checkout)
    job = request_release(checkout)
    (Path(checkout.other.workdir) / PATH).write_text(ORIGINAL.replace('Original', 'Remote change'))
    commit_all(checkout.other)
    checkout.other.remotes['origin'].push(['refs/heads/published:refs/heads/published'])
    with pytest.raises(PublicationError, match='Published content changed'):
        run(checkout, job, 'publish')
    checkout.prs.create.assert_not_called()


def test_edit_after_release_request_is_not_silently_published(checkout):
    save(checkout)
    job = request_release(checkout)
    save(checkout, EDITED.replace('Edited', 'Unreviewed'))
    with pytest.raises(PublicationError, match='changed after'):
        run(checkout, job, 'publish')
    checkout.prs.create.assert_not_called()


def test_revoked_writer_cannot_run_previously_queued_sync(checkout):
    save(checkout)
    job = reserve(checkout)
    checkout.user.is_active = False
    with pytest.raises(PublicationError, match='active writer'):
        run(checkout, job)


def test_task_failure_is_visible_and_retryable(checkout):
    save(checkout)
    job = reserve(checkout)
    task = tasks.DocumentTask()
    args = [job['generation'], 'scpub1', 'sync']
    task.on_failure(ValueError('conflict'), 'task', args, {}, None)
    assert checkout.service.status('scpub1')['sync']['can_retry']
    assert checkout.service.retry('scpub1', 'sync')['sync']['status'] == 'pending'


def test_existing_pull_request_accepts_updates_across_separate_submissions(checkout):
    save(checkout)
    first = request_release(checkout)
    run(checkout, first, 'publish')
    branch = 'publication-documents-scpub1-' + first['generation']
    checkout.prs.list_open.return_value = {branch: SimpleNamespace(number=1, html_url='https://example.test/pull/1')}

    other_id = document_id(OTHER)
    before = checkout.service.get('scpub1', other_id)
    other_content = ORIGINAL.replace('Original', 'Preface update')
    detail = checkout.service.save('scpub1', other_id, SimpleNamespace(content=other_content,
        revision=before['revision'], published_revision=before['published_revision']))
    checkout.service.publish('scpub1', [SimpleNamespace(id=other_id, revision=detail['revision'], published_revision=detail['published_revision'])])
    run(checkout, reserve(checkout, 'publish'), 'publish')

    latest = EDITED.replace('Edited', 'Further revision')
    save(checkout, latest)
    run(checkout, request_release(checkout), 'publish')
    tree = checkout.remote.lookup_reference('refs/heads/' + branch).peel(pygit2.Commit).tree
    assert tree[PATH].data.decode() == latest
    assert tree[OTHER].data.decode() == other_content
    assert 'refs/heads/' + branch not in checkout.published.references
    checkout.prs.create.assert_called_once()


def test_reverting_a_submitted_document_updates_the_existing_pull_request(checkout):
    save(checkout)
    first = request_release(checkout)
    run(checkout, first, 'publish')
    branch = 'publication-documents-scpub1-' + first['generation']
    checkout.prs.list_open.return_value = {branch: SimpleNamespace(number=1, html_url='https://example.test/pull/1')}
    save(checkout, ORIGINAL)
    listed = checkout.service.list('scpub1')['documents']
    assert next(doc for doc in listed if doc['id'] == checkout.uid)['request_outdated']
    assert checkout.service.get('scpub1', checkout.uid)['request_outdated']
    assert checkout.service.status('scpub1')['documents'][checkout.uid]['request_outdated']
    run(checkout, request_release(checkout), 'publish')
    tree = checkout.remote.lookup_reference('refs/heads/' + branch).peel(pygit2.Commit).tree
    assert tree[PATH].data.decode() == ORIGINAL


@pytest.mark.parametrize('later_publication', [False, True])
def test_merged_request_never_marks_later_drafts_or_publications_outdated(checkout, later_publication):
    save(checkout)
    first = request_release(checkout)
    run(checkout, first, 'publish')
    branch = 'publication-documents-scpub1-' + first['generation']
    merged = checkout.remote.lookup_reference('refs/heads/' + branch).target
    checkout.remote.references.create('refs/heads/published', merged, force=True)
    checkout.prs.get.return_value = SimpleNamespace(state='closed', merged=True)
    if later_publication:
        # Advance published again before the service ever observes the merge.
        checkout.other.remotes['origin'].fetch()
        checkout.other.reset(merged, pygit2.GIT_RESET_HARD)
        later = ORIGINAL.replace('Original', 'Later publication')
        (Path(checkout.other.workdir) / PATH).write_text(later)
        commit_all(checkout.other)
        checkout.other.remotes['origin'].push(['refs/heads/published:refs/heads/published'])
        (Path(checkout.work.workdir) / PATH).write_text(later)
    checkout.published.remotes['origin'].fetch()
    assert not checkout.service.get('scpub1', checkout.uid)['request_outdated']
    assert not save(checkout, ORIGINAL.replace('Original', 'Next draft'))['request_outdated']
    listed = checkout.service.list('scpub1')['documents']
    assert not next(doc for doc in listed if doc['id'] == checkout.uid)['request_outdated']
    status = checkout.service.status('scpub1')
    assert status['publish']['request_state'] == 'merged'
    assert not status['documents'][checkout.uid]['request_outdated']
    assert DocumentStore(checkout.work.workdir, 'scpub1').read()['submission']['state'] == 'merged'
    checkout.prs.get.assert_called_once_with(1)


def test_closed_request_can_be_reopened_without_losing_the_submitted_revision(checkout):
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    checkout.prs.get.return_value = SimpleNamespace(state='closed', merged=False)
    restored = save(checkout, ORIGINAL)
    assert not restored['request_outdated']
    with pytest.raises(PublicationError, match='No selected document'):
        request_release(checkout)
    store = DocumentStore(checkout.work.workdir, 'scpub1')
    state = store.read()
    assert state['submitted'][checkout.uid]['revision'] == revision(EDITED)
    state['submission']['checked_at'] = 0
    store.write(state)
    checkout.prs.get.return_value = SimpleNamespace(state='open', merged=False)
    assert checkout.service.get('scpub1', checkout.uid)['request_outdated']


def test_new_request_does_not_inherit_documents_from_the_previous_request(checkout):
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    checkout.prs.get.return_value = SimpleNamespace(state='closed', merged=False)
    checkout.service.status('scpub1')
    other_id = document_id(OTHER)
    before = checkout.service.get('scpub1', other_id)
    detail = checkout.service.save('scpub1', other_id, SimpleNamespace(content=EDITED,
        revision=before['revision'], published_revision=before['published_revision']))
    checkout.service.publish('scpub1', [SimpleNamespace(id=other_id, revision=detail['revision'],
        published_revision=detail['published_revision'])])
    checkout.prs.create.return_value = SimpleNamespace(number=2, html_url='https://example.test/pull/2')
    run(checkout, reserve(checkout, 'publish'), 'publish')
    state = DocumentStore(checkout.work.workdir, 'scpub1').read()
    assert state['submission']['number'] == 2
    assert list(state['submitted']) == [other_id]
    checkout.prs.get.return_value = SimpleNamespace(state='open', merged=False)
    assert not checkout.service.get('scpub1', checkout.uid)['request_outdated']


def test_existing_ledger_is_associated_with_its_recorded_request(checkout):
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    store = DocumentStore(checkout.work.workdir, 'scpub1')
    state = store.read()
    del state['submission']
    del state['publish']['request_number']
    store.write(state)
    checkout.prs.get.return_value = SimpleNamespace(state='closed', merged=True)
    detail = checkout.service.get('scpub1', checkout.uid)
    assert not detail['request_outdated']
    assert store.read()['submission']['state'] == 'merged'
    checkout.prs.get.assert_called_once_with(1)


def test_request_status_failure_does_not_prevent_saving_a_draft(checkout):
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    checkout.prs.get.side_effect = GithubException(503, 'unavailable', {})
    with pytest.raises(PublicationError, match='Unable to refresh'):
        checkout.service.status('scpub1')
    saved = checkout.service.save('scpub1', checkout.uid, SimpleNamespace(
        content=EDITED.replace('Edited', 'Offline draft'), revision=revision(EDITED),
        published_revision=revision(ORIGINAL)))
    assert saved['content'].find('Offline draft') != -1
    assert saved['request_outdated']
    assert DocumentStore(checkout.work.workdir, 'scpub1').read()['submission']['state'] == 'open'


def test_old_request_refresh_cannot_overwrite_a_new_request(checkout):
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    store = DocumentStore(checkout.work.workdir, 'scpub1')

    def replace_request(number):
        state = store.read()
        state['submission'] = {'number': 2, 'url': 'https://example.test/pull/2', 'state': 'open', 'checked_at': 0}
        store.write(state)
        return SimpleNamespace(state='closed', merged=True)

    checkout.prs.get.side_effect = replace_request
    checkout.service.status('scpub1')
    assert store.read()['submission']['number'] == 2
    assert store.read()['submission']['state'] == 'open'


def test_stale_open_response_cannot_revive_a_merged_request(checkout):
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    store = DocumentStore(checkout.work.workdir, 'scpub1')

    def delayed_open_response(number):
        state = store.read()
        state['submission']['state'] = 'merged'
        state['publish']['request_state'] = 'merged'
        store.write(state)
        return SimpleNamespace(state='open', merged=False)

    checkout.prs.get.side_effect = delayed_open_response
    assert checkout.service.status('scpub1')['publish']['request_state'] == 'merged'
    assert store.read()['submission']['state'] == 'merged'


def test_request_refresh_is_cached_and_observes_a_merge_after_expiry(checkout, monkeypatch):
    now = [1000]
    monkeypatch.setattr(document_requests, 'time', SimpleNamespace(time=lambda: now[0]))
    save(checkout)
    run(checkout, request_release(checkout), 'publish')
    assert checkout.service.status('scpub1')['publish']['request_state'] == 'open'
    checkout.prs.get.return_value = SimpleNamespace(state='closed', merged=True)
    now[0] += document_requests.REQUEST_REFRESH_SECONDS - 1
    assert checkout.service.status('scpub1')['publish']['request_state'] == 'open'
    checkout.prs.get.assert_called_once_with(1)
    now[0] += 1
    assert checkout.service.status('scpub1')['publish']['request_state'] == 'merged'
    assert checkout.prs.get.call_count == 2


def test_manual_changes_to_pr_target_are_not_overwritten(checkout):
    save(checkout)
    first = request_release(checkout)
    run(checkout, first, 'publish')
    branch = 'publication-documents-scpub1-' + first['generation']
    checkout.prs.list_open.return_value = {branch: SimpleNamespace(number=1, html_url='https://example.test/pull/1')}
    repo = checkout.other
    repo.remotes['origin'].fetch()
    parent = repo.lookup_reference('refs/remotes/origin/' + branch).peel(pygit2.Commit)
    tree = pygit2.Index(); tree.read_tree(parent.tree)
    tree.add(pygit2.IndexEntry(PATH, repo.create_blob(b'<article>Manual PR edit</article>'), 0o100644))
    sig = pygit2.Signature('Other editor', 'other@example.org')
    commit = repo.create_commit(None, sig, sig, 'manual', tree.write_tree(repo), [parent.id])
    repo.references.create('refs/heads/' + branch, commit)
    repo.remotes['origin'].push([f'refs/heads/{branch}:refs/heads/{branch}'])
    save(checkout, EDITED.replace('Edited', 'New revision'))
    with pytest.raises(PublicationError, match='other edits'):
        run(checkout, request_release(checkout), 'publish')
    assert checkout.remote.lookup_reference('refs/heads/' + branch).target == commit


def test_release_retries_pr_creation_after_branch_push_already_succeeded(checkout):
    save(checkout)
    job = request_release(checkout)
    checkout.prs.create.side_effect = [OSError('API interrupted'), SimpleNamespace(number=2, html_url='https://example.test/pull/2')]
    with pytest.raises(OSError, match='API interrupted'):
        run(checkout, job, 'publish')
    branch = 'publication-documents-scpub1-' + job['generation']
    assert 'refs/heads/' + branch not in checkout.published.references
    pushed = checkout.remote.lookup_reference('refs/heads/' + branch).target
    assert run(checkout, job, 'publish')
    assert 'refs/heads/' + branch not in checkout.published.references
    assert checkout.remote.lookup_reference('refs/heads/' + branch).target == pushed
    assert checkout.service.status('scpub1')['publish']['url'] == 'https://example.test/pull/2'


def test_completed_sync_files_are_not_carried_into_later_unrelated_saves(checkout):
    save(checkout)
    run(checkout, reserve(checkout))
    other_id = document_id(OTHER)
    before = checkout.service.get('scpub1', other_id)
    checkout.service.save('scpub1', other_id, SimpleNamespace(content=EDITED,
        revision=before['revision'], published_revision=before['published_revision']))
    assert list(DocumentStore(checkout.work.workdir, 'scpub1').read_sync()['documents']) == [other_id]


@pytest.mark.parametrize('operation,stage', [
    ('sync', 'unpublished-fetch'), ('sync', 'unpublished-push'), ('sync', 'index'),
    ('publish', 'unpublished-push'), ('publish', 'published-fetch'),
    ('publish', 'pr-list'), ('publish', 'pr-push'), ('publish', 'pr-create'),
])
def test_network_waits_allow_reads_and_saves_without_publishing_new_edits(checkout, monkeypatch, operation, stage):
    # An unrelated remote change exercises pull/merge and the ES indexing path.
    (Path(checkout.other.workdir) / 'unrelated.txt').write_text('remote edit')
    commit_all(checkout.other)
    checkout.other.remotes['origin'].push(['refs/heads/published:refs/heads/unpublished'])
    save(checkout)
    job = request_release(checkout) if operation == 'publish' else reserve(checkout)
    work = Path(checkout.work.workdir).resolve()
    lock = work.parent / '.publication-operations' / work.name / 'lock'
    reached, resume = Event(), Event()
    visited = []
    original_fetch, original_push = pygit2.Remote.fetch, GitManager.push
    fetch_count = 0

    def network(name):
        # Probe the kernel lock, bypassing checkout_lock's same-thread reentrancy.
        with lock.open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
        visited.append(name)
        if name == stage:
            reached.set()
            assert resume.wait(10), f'{stage} was not released'

    def fetch(remote, *args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        network('unpublished-fetch' if fetch_count == 1 else 'published-fetch')
        return original_fetch(remote, *args, **kwargs)

    def push(repo, *args, **kwargs):
        network('unpublished-push' if Path(repo.workdir).resolve() == work else 'pr-push')
        return original_push(repo, *args, **kwargs)

    def list_open():
        network('pr-list')
        return {}

    def create(**kwargs):
        network('pr-create')
        return SimpleNamespace(number=1, html_url='https://example.test/pull/1')

    newer_content = EDITED.replace('Edited', 'Newer saved draft')

    def read_and_save():
        assert checkout.service.status('scpub1')[operation]['status'] == 'syncing'
        assert checkout.service.counts() == {'scpub1': 2}
        assert len(checkout.service.list('scpub1')['documents']) == 2
        return save(checkout, newer_content)

    with monkeypatch.context() as patcher:
        patcher.setattr(pygit2.Remote, 'fetch', fetch)
        patcher.setattr(GitManager, 'push', staticmethod(push))
        patcher.setattr(tasks.es, 'update_indexes', Mock(side_effect=lambda *args, **kwargs: network('index')))
        patcher.setattr(checkout.prs, 'list_open', Mock(side_effect=list_open))
        patcher.setattr(checkout.prs, 'create', Mock(side_effect=create))
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(run, checkout, job, operation)
            try:
                assert reached.wait(5), f'{stage} was not reached'
                saved = pool.submit(read_and_save).result(timeout=3)
            finally:
                resume.set()
            assert running.result(timeout=5)

    assert stage in visited
    state = DocumentStore(work, 'scpub1').read()
    assert state['sync']['status'] == 'pending'
    assert state['sync']['documents'][checkout.uid]['revision'] == saved['revision']
    assert read_html(work / PATH) == newer_content
    assert checkout.remote.lookup_reference('refs/heads/unpublished').peel(pygit2.Commit).tree[PATH].data.decode() == EDITED
    if operation == 'sync':
        assert state['sync']['generation'] != job['generation']
    else:
        branch = 'publication-documents-scpub1-' + job['generation']
        assert checkout.remote.lookup_reference('refs/heads/' + branch).peel(pygit2.Commit).tree[PATH].data.decode() == EDITED
        assert state['publish']['status'] == 'synced'
        assert state['submitted'][checkout.uid]['revision'] == revision(EDITED)
        assert checkout.service.get('scpub1', checkout.uid)['request_outdated']
    assert run(checkout, reserve(checkout, task_id='new-sync'), task_id='new-sync')
    assert checkout.remote.lookup_reference('refs/heads/unpublished').peel(pygit2.Commit).tree[PATH].data.decode() == newer_content


@pytest.mark.parametrize('operation', ['sync', 'publish'])
def test_old_completion_preserves_a_reassigned_task(checkout, monkeypatch, operation):
    save(checkout)
    job = request_release(checkout) if operation == 'publish' else reserve(checkout)
    original_push = GitManager.push
    store = DocumentStore(checkout.work.workdir, 'scpub1', operation)

    def reassign(*args, **kwargs):
        with store.locked():
            state = store.read_sync()
            state.update(task_id='replacement', status='queued')
            store.write_sync(state)
        return original_push(*args, **kwargs)

    if operation == 'sync':
        monkeypatch.setattr(GitManager, 'push', staticmethod(reassign))
    else:
        def create(**kwargs):
            with store.locked():
                state = store.read_sync()
                state.update(task_id='replacement', status='queued')
                store.write_sync(state)
            return SimpleNamespace(number=1, html_url='https://example.test/pull/1')
        checkout.prs.create.side_effect = create
    assert run(checkout, job, operation)
    assert store.read_sync()['task_id'] == 'replacement'
    assert store.read_sync()['status'] == 'queued'
    if operation == 'publish':
        assert store.read()['submitted'][checkout.uid]['revision'] == revision(EDITED)


def test_remote_unpublished_edits_are_checked_in_the_committed_snapshot(checkout):
    base = '\n'.join(['<article>', '<h1 id="intro">Introduction</h1>', '<p>Original</p>',
                      '<p>Unchanged one</p>', '<p>Unchanged two</p>', '<p>Unchanged three</p>',
                      '<p>Ending</p>', '</article>', ''])
    (Path(checkout.work.workdir) / PATH).write_text(base)
    commit_all(checkout.work)
    checkout.work.remotes['origin'].push(['refs/heads/unpublished:refs/heads/unpublished',
                                          'refs/heads/unpublished:refs/heads/published'])
    checkout.published.remotes['origin'].fetch()
    checkout.other.remotes['origin'].fetch()
    checkout.other.reset(checkout.other.lookup_reference('refs/remotes/origin/published').target, pygit2.GIT_RESET_HARD)
    (Path(checkout.other.workdir) / PATH).write_text(base.replace('Ending', 'Remote addition'))
    commit_all(checkout.other)
    checkout.other.remotes['origin'].push(['refs/heads/published:refs/heads/unpublished'])
    save(checkout, base.replace('Original', 'Edited'))
    job = request_release(checkout)
    with pytest.raises(PublicationError, match='Remote changes were merged'):
        run(checkout, job, 'publish')
    checkout.prs.create.assert_not_called()
    assert 'Remote addition' in read_html(Path(checkout.work.workdir) / PATH)


def test_completion_preserves_request_state_refreshed_during_publish(checkout):
    save(checkout)
    first = request_release(checkout)
    run(checkout, first, 'publish')
    branch = 'publication-documents-scpub1-' + first['generation']
    checkout.prs.list_open.return_value = {branch: SimpleNamespace(number=1, html_url='https://example.test/pull/1')}
    save(checkout, EDITED.replace('Edited', 'Further revision'))
    job = request_release(checkout)
    store = DocumentStore(checkout.work.workdir, 'scpub1')

    def list_open():
        # A status poll may observe the previous PR being merged while this task is running.
        with store.locked():
            state = store.read()
            state['submission'].update(state='merged', checked_at=123)
            store.write(state)
        return {branch: SimpleNamespace(number=1, html_url='https://example.test/pull/1')}

    checkout.prs.list_open.side_effect = list_open
    assert run(checkout, job, 'publish')
    assert store.read()['submission']['state'] == 'merged'
    assert store.read()['publish']['request_state'] == 'merged'
