"""Shared periodic recovery with real stores and a simulated task broker."""
import asyncio
import fcntl
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import pytest
from kombu.exceptions import OperationalError
from search.search import Search

from app.db.schemas.user import UserBase
from app.services import sync_dispatch as dispatcher
from app.services.publications.store import PublicationStore
from app.services.tags.service import TagService

with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app import tasks

USER = UserBase(github_id=123, username='admin', email='admin@example.org', avatar_url=None, role='administrator')


@pytest.fixture
def pending_syncs(tmp_path, monkeypatch):
    work = tmp_path / 'unpublished'
    work.mkdir()
    publications = PublicationStore(work)
    with publications.locked():
        publications.save([], {}, USER.model_dump())
    tags = TagService(work)
    tags.mutate('create', USER, data={'tag': 'first'})
    publication_queue, tag_queue = Mock(), Mock()
    monkeypatch.setattr(tasks.sync_publications, 'apply_async', publication_queue)
    monkeypatch.setattr(tasks.sync_tags, 'apply_async', tag_queue)
    return publications, tags, publication_queue, tag_queue


@pytest.mark.asyncio
async def test_loop_dispatches_both_on_start_and_checks_again_after_60_seconds(pending_syncs, monkeypatch):
    publications, tags, publication_queue, tag_queue = pending_syncs
    intervals = []

    async def sleep(delay):
        intervals.append(delay)
        assert delay == 60
        publication_queue.assert_called_once()
        if len(intervals) == 1:
            tag_queue.assert_called_once()
            tags.mutate('create', USER, data={'tag': 'second'})
        else:
            assert tag_queue.call_count == 2
            raise asyncio.CancelledError

    monkeypatch.setattr(dispatcher.asyncio, 'sleep', sleep)
    with pytest.raises(asyncio.CancelledError):
        await dispatcher.dispatch_loop(publications.work)
    assert intervals == [60, 60]


@pytest.mark.parametrize('broken', ['publications', 'tags'])
def test_one_store_failure_does_not_stop_other_domain(pending_syncs, monkeypatch, broken):
    publications, tags, publication_queue, tag_queue = pending_syncs
    store = publications if broken == 'publications' else tags.store
    failed_queue, other_queue = ((publication_queue, tag_queue) if broken == 'publications'
                                 else (tag_queue, publication_queue))
    with monkeypatch.context() as failure:
        failure.setattr(type(store), 'read_sync', Mock(side_effect=OSError('storage unavailable')))
        dispatcher.dispatch_all(publications.work)
    failed_queue.assert_not_called()
    other_queue.assert_called_once()
    dispatcher.dispatch_all(publications.work)
    failed_queue.assert_called_once()
    other_queue.assert_called_once()


def test_parallel_checks_reserve_each_delivery_once(pending_syncs):
    publications, tags, publication_queue, tag_queue = pending_syncs
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(dispatcher.dispatch_all, [publications.work, publications.work]))
    for store, queue in [(publications, publication_queue), (tags.store, tag_queue)]:
        queue.assert_called_once()
        state = store.read_sync()
        assert state['status'] == 'queued'
        assert queue.call_args.kwargs == {
            'args': [state['generation']], 'task_id': state['task_id'], 'retry': False}


@pytest.mark.parametrize('broken', ['publications', 'tags'])
def test_broker_failure_retries_without_blocking_other_domain(pending_syncs, monkeypatch, broken):
    publications, tags, publication_queue, tag_queue = pending_syncs
    store = publications if broken == 'publications' else tags.store
    failed_queue, other_queue = ((publication_queue, tag_queue) if broken == 'publications'
                                 else (tag_queue, publication_queue))
    failed_queue.side_effect = OperationalError('broker offline')
    monkeypatch.setattr(dispatcher.time, 'time', lambda: 100)
    dispatcher.dispatch_all(publications.work)
    assert store.read_sync()['status'] == 'pending'
    assert store.read_sync()['dispatch_after'] == 100 + dispatcher.DISPATCH_RETRY_DELAY
    other_queue.assert_called_once()
    failed_queue.side_effect = None
    dispatcher.dispatch_all(publications.work)
    failed_queue.assert_called_once()
    monkeypatch.setattr(dispatcher.time, 'time', lambda: 160)
    dispatcher.dispatch_all(publications.work)
    assert failed_queue.call_count == 2
    assert store.read_sync()['status'] == 'queued'
    other_queue.assert_called_once()


def test_delivery_is_reserved_and_checkout_lock_released_before_broker(pending_syncs):
    publications, tags, publication_queue, tag_queue = pending_syncs

    def send(store, **kwargs):
        with (publications.directory / 'lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = store.read_sync()
            assert state['status'] == 'queued'
            assert state['task_id'] == kwargs['task_id']

    publication_queue.side_effect = lambda **kwargs: send(publications, **kwargs)
    tag_queue.side_effect = lambda **kwargs: send(tags.store, **kwargs)
    dispatcher.dispatch_all(publications.work)
    publication_queue.assert_called_once()
    tag_queue.assert_called_once()
