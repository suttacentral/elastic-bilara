"""Real file locks and deterministic ES delays; no external search requests."""
import fcntl
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from search import search as search_module
from search.search import Search
from search.utils import create_doc_id

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services import storage
from app.services.projects.models import StructureCommitIn

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app.api.api_v1.endpoints import tags
    from app.services.projects import utils as projects
    from app.services.projects import structure_service

USER = UserBase(github_id=123, username='alice', email='alice@example.org',
                avatar_url=None, role='administrator')


def checkout_locked(work):
    lock = work.parent / '.publication-operations' / work.name / 'lock'
    with lock.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


@pytest.fixture
def env(tmp_path, monkeypatch):
    work = tmp_path / 'unpublished'
    root = work / 'root/pli/ms/sutta/sn1_root-pli-ms.json'
    root.parent.mkdir(parents=True)
    root.write_text(json.dumps({'sn1:1': 'root', 'sn1:2': 'root'}))
    (work / '_tags.json').write_text(json.dumps([{'tag': 'new'}]))
    target = work / 'tag/pli/ms/sutta/sn1_tag.json'
    monkeypatch.setattr(settings, 'WORK_DIR', work)
    search = object.__new__(Search)
    search._batch_size = 125
    search._search = Mock()
    documents = {}

    def index(*, index, id, body, **kwargs):
        documents[index, id] = deepcopy(body)

    def bulk(client, actions, **kwargs):
        for action in actions:
            key = action['_index'], action['_id']
            if action.get('_op_type') == 'delete':
                documents.pop(key, None)
            else:
                documents[key] = deepcopy(action['_source'])
        return len(actions), []

    def delete_by_query(*, index, body):
        query = body['query']
        field, value = next(iter(next(iter(query.values())).items()))
        for key, source in list(documents.items()):
            if key[0] == index and source.get(field) == value:
                del documents[key]

    def lookup(**kwargs):
        assert checkout_locked(work)
        return {str(root)}

    search._search.index.side_effect = index
    search._search.get.side_effect = lambda *, index, id: {'_source': deepcopy(documents[index, id])}
    search._search.delete_by_query.side_effect = delete_by_query
    monkeypatch.setattr(search_module.helpers, 'bulk', bulk)
    monkeypatch.setattr(search, 'get_file_paths', Mock(side_effect=lookup))
    monkeypatch.setattr(tags, 'search', search)
    monkeypatch.setattr(projects, 'search', search)
    monkeypatch.setattr(projects, 'get_user', lambda _: USER)
    monkeypatch.setattr(projects, '_schedule_file_commit', Mock(return_value='task'))
    monkeypatch.setattr(structure_service, 'schedule_split_merge_auto_publish', Mock(return_value=projects.SplitMergePublishResult(
        task_id='task', auto_published_paths=[], manual_publish_paths=[])))
    monkeypatch.setattr(tags, 'create_indexed_directory', lambda path: path.mkdir(parents=True, exist_ok=True))
    return SimpleNamespace(work=work, root=root, target=target, search=search,
                           documents=documents, index=index)


def delay_first_index(env):
    entered, release = Event(), Event()

    def index(**kwargs):
        if not entered.is_set():
            assert checkout_locked(env.work)
            entered.set()
            assert release.wait(5), 'test did not release delayed ES request'
        env.index(**kwargs)

    env.search._search.index.side_effect = index
    return entered, release


@pytest.mark.parametrize('operation', ['duplicate', 'edit', 'structure'])
def test_creation_serializes_with_other_checkout_writers(env, operation):
    entered, release = delay_first_index(env)
    started = Event()

    def following_operation():
        started.set()
        if operation == 'duplicate':
            assert 'already exists' in tags.create_tag_data_file(USER, 'sn1')['detail']
        elif operation == 'edit':
            assert projects.update_file(env.target, {'sn1:1': 'new'}, env.root, USER) == (True, None, 'task')
        else:
            preview = structure_service.preview(env.root, 'merge', 'sn1:1')
            payload = StructureCommitIn(
                muid='root-pli-ms', prefix='sn1', operation='merge', uid='sn1:1',
                operation_id=uuid4(), revision=preview['revision'],
                edits={'tag-pli-ms': {'sn1:1': 'new'}}, reviewed=preview['manual_projects'])
            result = structure_service.commit_operation(env.root, payload, env.search, USER)
            assert result['status'] == 'complete'

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(tags.create_tag_data_file, USER, 'sn1')
        try:
            assert entered.wait(3)
            second = executor.submit(following_operation)
            assert started.wait(3)
            assert not second.done()
        finally:
            release.set()
        assert 'created' in first.result(timeout=3)['detail']
        second.result(timeout=3)

    expected = {'sn1:1': '', 'sn1:2': ''} if operation == 'duplicate' else {'sn1:1': 'new', 'sn1:2': ''}
    if operation == 'structure':
        expected.pop('sn1:2')
        assert json.loads(env.root.read_text()) == {'sn1:1': 'rootroot'}
    assert json.loads(env.target.read_text()) == expected
    main = env.documents[settings.ES_INDEX, create_doc_id(env.target)]
    assert main['segments'] == [{'uid': uid, 'segment': value} for uid, value in expected.items()]
    for uid, value in expected.items():
        assert env.documents[settings.ES_SEGMENTS_INDEX, create_doc_id(env.target, uid)]['segment'] == value
    if operation == 'structure':
        assert (settings.ES_SEGMENTS_INDEX, create_doc_id(env.target, 'sn1:2')) not in env.documents
    assert not checkout_locked(env.work)


def test_stale_root_index_returns_not_found_without_creating_file(env):
    env.root.unlink()
    with pytest.raises(HTTPException) as error:
        tags.create_tag_data_file(USER, 'sn1')
    assert error.value.status_code == 404
    assert not env.target.exists()
    env.search._search.index.assert_not_called()


def test_failed_index_preserves_file_releases_lock_and_allows_retry(env, monkeypatch):
    index = env.search.add_to_index
    monkeypatch.setattr(env.search, 'add_to_index', Mock(return_value=(False, RuntimeError('ES unavailable'))))
    with pytest.raises(HTTPException) as error:
        tags.create_tag_data_file(USER, 'sn1')
    assert error.value.status_code == 503
    assert env.target.exists()
    assert not checkout_locked(env.work)

    monkeypatch.setattr(env.search, 'add_to_index', index)
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert 'already exists' in executor.submit(tags.create_tag_data_file, USER, 'sn1').result(timeout=3)['detail']
    assert env.documents[settings.ES_INDEX, create_doc_id(env.target)]['segments']


@pytest.fixture
def client(env):
    api = FastAPI()
    api.include_router(tags.router)
    api.dependency_overrides[tags.utils.get_current_user] = lambda: USER
    api.dependency_overrides[tags.is_admin_or_superuser] = lambda: USER
    api.dependency_overrides[tags.is_user_active] = lambda: USER
    with TestClient(api, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize('broken', [b'{"sn1:1":', b'null', b'[]', b'"text"',
                                   b'{"sn1:1": null}', b'{"sn1:1": 1}', b'\xff'])
def test_existing_invalid_tag_file_returns_conflict_without_overwrite(env, client, broken):
    env.target.parent.mkdir(parents=True)
    env.target.write_bytes(broken)
    response = client.post('/tags/data/sn1/')
    assert response.status_code == 409
    assert 'Repair the file' in response.json()['detail']
    assert env.target.read_bytes() == broken
    env.search.get_file_paths.assert_not_called()
    env.search._search.index.assert_not_called()
    assert not env.documents


@pytest.mark.parametrize('failure', ['dump', 'file_fsync', 'replace', 'directory_fsync'])
def test_atomic_creation_storage_failure_is_retryable(env, client, monkeypatch, failure):
    original_fsync = storage.os.fsync
    fsync_calls = 0

    def interrupted_dump(value, handle, **kwargs):
        handle.write('{"sn1:1":')
        handle.flush()
        raise OSError('interrupted JSON write')

    def failing_fsync(fd):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == (1 if failure == 'file_fsync' else 2):
            raise OSError('fsync failed')
        original_fsync(fd)

    with monkeypatch.context() as patcher:
        if failure == 'dump':
            patcher.setattr(storage.json, 'dump', interrupted_dump)
        elif failure == 'replace':
            patcher.setattr(storage.os, 'replace', Mock(side_effect=OSError('replace failed')))
        else:
            patcher.setattr(storage.os, 'fsync', failing_fsync)
        response = client.post('/tags/data/sn1/')
    assert response.status_code == 503
    assert 'storage is unavailable' in response.json()['detail']
    env.search._search.index.assert_not_called()
    assert not checkout_locked(env.work)
    expected = {'sn1:1': '', 'sn1:2': ''}
    if failure == 'directory_fsync':
        # Replacement already happened; retry must use the complete existing file.
        assert json.loads(env.target.read_text()) == expected
        assert list(env.target.parent.iterdir()) == [env.target]
    else:
        assert not env.target.exists()
        assert list(env.target.parent.iterdir()) == []

    response = client.post('/tags/data/sn1/')
    assert response.status_code == 201
    assert json.loads(env.target.read_text()) == expected
    assert env.documents[settings.ES_INDEX, create_doc_id(env.target)]['segments'] == [
        {'uid': uid, 'segment': value} for uid, value in expected.items()]


def test_existing_valid_tag_file_retains_assignments_when_reindexed(env, client):
    env.target.parent.mkdir(parents=True)
    original = b'{"sn1:1": "new", "sn1:2": ""}\n'
    env.target.write_bytes(original)
    response = client.post('/tags/data/sn1/')
    assert response.status_code == 201
    assert 'already exists' in response.json()['detail']
    assert env.target.read_bytes() == original
    assert env.documents[settings.ES_INDEX, create_doc_id(env.target)]['segments'][0]['segment'] == 'new'


def test_index_file_read_failure_preserves_file_and_allows_retry(env, client, monkeypatch):
    with monkeypatch.context() as patcher:
        patcher.setattr(search_module.utils, 'get_json_data', Mock(side_effect=OSError('read failed')))
        response = client.post('/tags/data/sn1/')
    assert response.status_code == 503
    assert json.loads(env.target.read_text()) == {'sn1:1': '', 'sn1:2': ''}
    assert not checkout_locked(env.work)
    env.search._search.index.assert_not_called()
    assert client.post('/tags/data/sn1/').status_code == 201
