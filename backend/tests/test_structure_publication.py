"""Publication contract, using a local remote without GitHub or Elasticsearch."""
from pathlib import Path
from unittest.mock import Mock, patch

import pygit2
import pytest
from search.search import Search

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app import tasks
    from app.services.projects import utils
    from app.services.git.manager import GitManager


@pytest.mark.parametrize('operation', ['split', 'merge'])
def test_every_type_is_queued_in_one_task(tmp_path, operation):
    kinds = ['root', 'translation', 'comment', 'html', 'reference', 'variant', 'tag', 'future']
    paths = [Path(kind) / 'dn1.json' for kind in kinds]
    user = Mock(github_id=1, username='admin')
    with patch.object(utils.settings, 'WORK_DIR', tmp_path), patch.object(utils, 'get_user', return_value=user), patch.object(utils, 'commit') as commit:
        commit.delay.return_value.id = 'task'
        result = utils.schedule_split_merge_auto_publish(user, paths + paths, operation)
    assert result.auto_published_paths == ['/' + str(p) for p in paths]
    assert result.manual_publish_paths == []
    commit.delay.assert_called_once_with(user.model_dump(), [str(p) for p in paths],
                                         f'admin {operation} split/merge files')


def test_push_retry_sends_all_files_after_local_commit(tmp_path):
    remote = pygit2.init_repository(str(tmp_path / 'remote.git'), bare=True)
    repo = pygit2.init_repository(str(tmp_path / 'work'), initial_head='unpublished')
    author = pygit2.Signature('test', 'test@example.com')
    repo.create_commit('HEAD', author, author, 'initial', repo.index.write_tree(), [])
    repo.remotes.create('origin', str(tmp_path / 'remote.git'))
    repo.remotes['origin'].push(['refs/heads/unpublished'])
    initial = remote.references['refs/heads/unpublished'].target
    paths = [Path(kind) / 'dn1.json' for kind in ['root', 'translation', 'comment', 'html', 'reference', 'variant', 'tag']]
    for relative in paths + [Path('translation/dn2.json')]:
        path = Path(repo.workdir) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"dn1:1.1": "new structure"}')
    manager = GitManager.__new__(GitManager)
    manager.unpublished = repo
    manager.author = manager.committer = author
    push = GitManager.push
    with patch.object(tasks, 'GitManager', wraps=GitManager) as factory, patch.object(tasks, 'UserBase'), patch.object(tasks, 'es'):
        factory.return_value = manager
        factory.push.side_effect = pygit2.GitError('connection lost')
        with pytest.raises(pygit2.GitError):
            tasks.commit.run({}, [str(p) for p in paths], 'structure')
        committed = repo.head.target
        assert committed != initial
        assert remote.references['refs/heads/unpublished'].target == initial
        factory.push.side_effect = push
        assert tasks.commit.run({}, [str(p) for p in paths], 'structure') is True
    assert repo.head.target == committed
    assert remote.references['refs/heads/unpublished'].target == committed
    tree = remote[committed].tree
    for path in paths:
        assert remote[tree[str(path)].id].data == (Path(repo.workdir) / path).read_bytes()
    with pytest.raises(KeyError):
        tree['translation/dn2.json']


@pytest.mark.parametrize('failure_point', ['write_tree', 'create_commit'])
@pytest.mark.parametrize('error_type', [pygit2.GitError, OSError])
def test_commit_failure_stops_before_pull_and_push(failure_point, error_type):
    manager = Mock()
    error = error_type('commit write failed')
    if failure_point == 'write_tree':
        manager.unpublished.index.write_tree.side_effect = error
    else:
        manager.unpublished.create_commit.side_effect = error

    with patch.object(tasks, 'GitManager', wraps=GitManager) as factory, \
            patch.object(GitManager, 'has_status_changed', return_value=True), \
            patch.object(tasks, 'UserBase'), patch.object(tasks, 'es') as es:
        factory.return_value = manager
        factory.add.return_value = True

        with pytest.raises(error_type) as raised:
            tasks.commit.run({}, ['root/dn1.json'], 'structure')

        assert raised.value is error
        factory.commit.assert_called_once()
        manager.pull.assert_not_called()
        factory.push.assert_not_called()
        es.update_indexes.assert_not_called()


def test_empty_file_set_does_not_queue_a_commit():
    with patch.object(utils, 'commit') as commit:
        result = utils.schedule_split_merge_auto_publish(Mock(), [], 'split')
    commit.delay.assert_not_called()
    assert result.task_id is None
    assert result.auto_published_paths == []
