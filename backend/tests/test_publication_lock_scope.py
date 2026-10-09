"""Exercise real flock boundaries without GitHub or Elasticsearch requests."""
import fcntl
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import pygit2
import pytest
from search.search import Search

from app.services.publications.store import PUBLICATION_FILES, PublicationStore, write_json

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app import tasks
    from app.services.git.manager import GitManager


def is_locked(store):
    """An independent descriptor must compete with the actual OS lock."""
    store.directory.mkdir(parents=True, exist_ok=True)
    with (store.directory / 'lock').open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


@pytest.fixture
def store(tmp_path):
    work = tmp_path / 'unpublished'
    work.mkdir()
    return PublicationStore(work)


def pending_pair(store):
    pair = dict(zip(PUBLICATION_FILES, ([{'publication_number': 'scpub1'}],
                                      {'scpub1': {'publication_number': 'scpub1'}})))
    store.directory.mkdir(parents=True, exist_ok=True)
    write_json(store.journal, pair)
    return pair


@pytest.mark.parametrize('task_name,add', [('commit', True), ('commit', False), ('pr', True)])
def test_tasks_lock_local_commit_and_release_before_external_work(store, task_name, add):
    pair = pending_pair(store)
    manager = Mock()
    manager.unpublished.workdir = str(store.work)
    manager.separate_existing_files.return_value = ([Path('present.json')], [Path('deleted.json')])
    calls = []

    def check(name, locked, result=None):
        def operation(*args, **kwargs):
            assert is_locked(store) is locked, name
            for filename, expected in pair.items():
                assert json.loads((store.work / filename).read_text()) == expected
            calls.append(name)
            return result
        return operation

    with patch.object(tasks, 'GitManager') as factory, patch.object(tasks, 'UserBase'), \
            patch.object(tasks, 'es') as es:
        factory.return_value = manager
        factory.add.side_effect = check('add', True, True)
        factory.remove.side_effect = check('remove', True, True)
        factory.commit.side_effect = check('commit', True, True)
        # pull must start unlocked so its fetch can proceed without blocking readers.
        manager.pull.side_effect = check('pull', False, [])
        factory.push.side_effect = check('push', False)
        es.update_indexes.side_effect = check('index', False)
        manager.publish_files.side_effect = check('publish', False, 'pr-url')
        if task_name == 'commit':
            assert tasks.commit.run({}, list(PUBLICATION_FILES), 'metadata', add=add)
            assert calls == ['add' if add else 'remove', 'commit', 'pull', 'push', 'index', 'index']
        else:
            assert tasks.pr.run({}, list(PUBLICATION_FILES)) == 'pr-url'
            assert calls == ['add', 'commit', 'pull', 'push', 'publish']
    assert not is_locked(store)


@pytest.mark.parametrize('task_name', ['commit', 'pr'])
def test_failed_local_commit_releases_lock_and_stops_external_work(store, task_name):
    manager = Mock()
    manager.unpublished.workdir = str(store.work)
    with patch.object(tasks, 'GitManager') as factory, patch.object(tasks, 'UserBase'), \
            patch.object(tasks, 'es') as es:
        factory.return_value = manager
        factory.commit.side_effect = OSError('write failed')
        args = ({}, list(PUBLICATION_FILES), 'metadata') if task_name == 'commit' else ({}, list(PUBLICATION_FILES))
        with pytest.raises(OSError, match='write failed'):
            getattr(tasks, task_name).run(*args)
        manager.pull.assert_not_called()
        factory.push.assert_not_called()
        manager.publish_files.assert_not_called()
        es.update_indexes.assert_not_called()
    assert not is_locked(store)


def pull_manager(work):
    manager = GitManager.__new__(GitManager)
    manager.author = manager.committer = Mock()
    branch = Mock(workdir=str(work))
    manager.unpublished = branch
    remote = Mock()
    remote.name = 'origin'
    branch.remotes = [remote]
    branch.head.shorthand = 'unpublished'
    branch.lookup_reference.return_value.target = pygit2.Oid(hex='1' * 40)
    branch.index.conflicts = None
    manager.get_filenames_from_diff = Mock(return_value=[])
    return manager, branch, remote


@pytest.mark.parametrize('mode', ['up_to_date', 'fast_forward', 'merge', 'force', 'conflict'])
def test_pull_fetches_unlocked_then_recovers_and_merges_locked(store, mode):
    pair = pending_pair(store)
    manager, branch, remote = pull_manager(store.work)
    analysis = {
        'up_to_date': pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE,
        'fast_forward': pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD,
    }.get(mode, pygit2.GIT_MERGE_ANALYSIS_NORMAL)
    branch.merge_analysis.return_value = (analysis, None)
    if mode == 'conflict':
        branch.index.conflicts = [('ours', 'theirs')]

    def fetch():
        assert not is_locked(store)
        # Another local commit can complete during the network request.
        branch.revparse_single.return_value.id = 'head-after-fetch'
        assert json.loads(store.journal.read_text()) == pair

    def locked(*args, **kwargs):
        assert is_locked(store)
        assert json.loads(store.journal.read_text()) is None
        for filename, expected in pair.items():
            assert json.loads((store.work / filename).read_text()) == expected

    remote.fetch.side_effect = fetch
    for operation in [branch.state_cleanup, branch.revparse_single, branch.merge_analysis,
                      branch.checkout_tree, branch.merge, branch.index.write_tree, branch.create_commit]:
        operation.side_effect = locked
    # Preserve mock return values after checking the lock.
    branch.revparse_single.side_effect = lambda *a: (locked(), branch.revparse_single.return_value)[1]
    branch.merge_analysis.side_effect = lambda *a: (locked(), (analysis, None))[1]
    if mode == 'conflict':
        with pytest.raises(pygit2.GitError, match='local conflict'):
            manager.pull(branch)
    else:
        assert manager.pull(branch, force=mode == 'force') == []
    remote.fetch.assert_called_once()
    assert manager.get_filenames_from_diff.call_args.args[0] == 'head-after-fetch'
    assert not is_locked(store)


def test_published_pull_proceeds_while_unpublished_is_locked(store, tmp_path):
    manager, branch, remote = pull_manager(tmp_path / 'published')
    # A separate Repository object for another checkout must not share the lock.
    manager.unpublished = Mock(workdir=str(store.work))
    branch.head.shorthand = 'published'
    branch.merge_analysis.return_value = (pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD, None)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with store.locked():
            result = executor.submit(manager.pull, branch)
            assert result.result(timeout=2) == []
    remote.fetch.assert_called_once()
    branch.checkout_tree.assert_called_once()
