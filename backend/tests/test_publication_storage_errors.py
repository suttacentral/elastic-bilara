"""Storage failures are typed without absorbing errors from lock callers."""
import fcntl
from pathlib import Path

import pytest

from app.services.publications import store as storage
from app.services.publications.errors import PublicationStorageError


@pytest.mark.parametrize('failure_site', ['open', 'lock', 'unlock', 'read', 'recover', 'write'])
def test_storage_io_errors_preserve_their_cause(tmp_path, monkeypatch, failure_site):
    store = storage.PublicationStore(tmp_path)
    storage.write_json(tmp_path / storage.PUBLICATION_FILES[0], [])
    storage.write_json(tmp_path / storage.PUBLICATION_FILES[1], {})
    store.directory.mkdir(parents=True)
    storage.write_json(store.journal, None)
    error = OSError('simulated storage failure')
    if failure_site == 'open':
        original = Path.open

        def fail_open(path, *args, **kwargs):
            if path == store.directory / 'lock':
                raise error
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'open', fail_open)
    elif failure_site in ('lock', 'unlock'):
        original = fcntl.flock

        def fail_flock(handle, operation):
            if operation == (fcntl.LOCK_EX if failure_site == 'lock' else fcntl.LOCK_UN):
                raise error
            return original(handle, operation)

        monkeypatch.setattr(fcntl, 'flock', fail_flock)
    elif failure_site in ('read', 'recover'):
        original = Path.read_text
        target = store.journal if failure_site == 'recover' else tmp_path / storage.PUBLICATION_FILES[0]

        def fail_read(path, *args, **kwargs):
            if path == target:
                raise error
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'read_text', fail_read)
    else:
        def fail_replace(*args):
            raise error

        monkeypatch.setattr(storage.os, 'replace', fail_replace)

    with pytest.raises(PublicationStorageError) as raised:
        with store.locked():
            if failure_site == 'write':
                store.save([], {})
            else:
                store.read()
    assert raised.value.__cause__ is error
    # GitTask retries OSError, including the storage-specific subtype.
    assert isinstance(raised.value, OSError)
    monkeypatch.undo()
    # Failures must release both the OS lock and the thread-local nesting state.
    with (store.directory / 'lock').open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(handle, fcntl.LOCK_UN)
    with store.locked():
        assert store.read() == ([], {})


def test_nested_lock_propagates_callers_oserror_unchanged(tmp_path):
    store = storage.PublicationStore(tmp_path)
    error = OSError('git operation failed')
    with pytest.raises(OSError) as raised:
        with store.locked():
            with store.locked():
                raise error
    assert raised.value is error
    assert not isinstance(raised.value, PublicationStorageError)
