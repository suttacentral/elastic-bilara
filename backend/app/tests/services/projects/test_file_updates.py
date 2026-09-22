import json
import multiprocessing
import stat
import threading
import time
import builtins
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.projects import utils as project_utils
from app.services.projects.file_coordinator import project_file_lock
from app.services.projects.virtual_projects import VirtualProjectFile
from app.services.projects.structure_store import StructureStore, StructureConflict
from search.utils import create_doc_id


@pytest.mark.parametrize("mode", ["existing", "materialized"])
@pytest.mark.parametrize("size", [10, 1000])
@pytest.mark.parametrize("patch", [{"uid:0": "changed"}, {"uid:0": ""},
                                    {"uid:0": "changed", "uid:1": "second"}])
def test_save_indexes_only_submitted_segments(tmp_path, monkeypatch, mode, size, patch):
    monkeypatch.setattr(project_utils.settings, "WORK_DIR", tmp_path)
    root = tmp_path / "root.json"
    target = tmp_path / "translation.json"
    original = {f"uid:{i}": f"text {i}" for i in range(size)}
    root.write_text(json.dumps(original))
    target.write_text(json.dumps(original))
    user = SimpleNamespace(github_id="1")
    monkeypatch.setattr(project_utils, "get_user", lambda _: user)
    monkeypatch.setattr(project_utils, "_schedule_file_commit", lambda *_: "task")
    monkeypatch.setattr(project_utils, "sort_data", lambda data, _: data)

    main_index = project_utils.settings.ES_INDEX
    segments_index = project_utils.settings.ES_SEGMENTS_INDEX
    main_id = create_doc_id(target)
    documents = {(main_index, main_id): {
        "segments": [{"uid": uid, "segment": text} for uid, text in original.items()]
    }}
    documents.update({(segments_index, create_doc_id(target, uid)): {
        "uid": uid, "segment": text, "muid": "translation-en-test"
    } for uid, text in original.items()})

    def index(*, index, id, body):
        documents[index, id] = deepcopy(body)

    transport = Mock()
    transport.get.side_effect = lambda *, index, id: {"_source": deepcopy(documents[index, id])}
    transport.index.side_effect = index
    # Exercise the real index-update methods, replacing only the ES transport.
    monkeypatch.setattr(project_utils.search, "_search", transport)
    revision = StructureStore(tmp_path, root).revision()
    if mode == "existing":
        result = project_utils.update_file(target, patch, root, user, revision)
    else:
        virtual = VirtualProjectFile(root, "root-pli-ms", target, "translation-en-test", "test")
        result = project_utils.materialize_translation_file(virtual, patch, user, revision)

    assert result[:3] == (True, None, "task")
    expected = original | patch
    assert json.loads(target.read_text()) == expected
    assert {item["uid"]: item["segment"] for item in documents[main_index, main_id]["segments"]} == expected
    assert {uid: documents[segments_index, create_doc_id(target, uid)]["segment"] for uid in original} == expected
    expected_ids = [main_id, *(create_doc_id(target, uid) for uid in patch)]
    assert [call.kwargs["id"] for call in transport.get.call_args_list] == expected_ids
    assert [call.kwargs["id"] for call in transport.index.call_args_list] == expected_ids


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_incremental_save_rolls_back_index_when_file_write_fails(tmp_path, monkeypatch, rollback_fails):
    monkeypatch.setattr(project_utils.settings, "WORK_DIR", tmp_path)
    root = tmp_path / "root.json"
    target = tmp_path / "translation.json"
    original = {"uid:1": "original", "uid:2": "kept"}
    root.write_text(json.dumps(original))
    target.write_text(json.dumps(original))
    user = SimpleNamespace(github_id="1")
    monkeypatch.setattr(project_utils, "get_user", lambda _: user)
    commit = Mock()
    monkeypatch.setattr(project_utils, "_schedule_file_commit", commit)
    file_error = OSError("write failed")
    monkeypatch.setattr(project_utils, "write_json_data", Mock(return_value=(False, file_error)))
    rollback = (False, RuntimeError("index unavailable")) if rollback_fails else (True, None)
    index = Mock(side_effect=[(True, None), rollback])
    monkeypatch.setattr(project_utils.search, "update_segments", index)

    updated, error, task_id = project_utils.update_file(target, {"uid:1": ""}, root, user)

    assert updated is False
    assert task_id is None
    assert index.call_args_list[0].args == (target, {"uid:1": ""})
    assert index.call_args_list[1].args == (target, original)
    if rollback_fails:
        assert "write failed; search rollback failed: index unavailable" in str(error)
    else:
        assert error is file_error
    assert json.loads(target.read_text()) == original
    commit.assert_not_called()


@pytest.mark.parametrize("mode", ["existing", "virtual", "materialized"])
@pytest.mark.parametrize("change", [None, "order", "epoch", "unknown_uid"])
def test_save_reuses_root_for_revision_and_uid_validation(tmp_path, monkeypatch, mode, change):
    monkeypatch.setattr(project_utils.settings, "WORK_DIR", tmp_path)
    root = tmp_path / "root.json"
    target = tmp_path / "translation.json"
    root.write_text(json.dumps({"uid:1": "A", "uid:2": "B"}))
    original = {"uid:1": "", "uid:2": "kept"}
    if mode != "virtual":
        target.write_text(json.dumps(original))
    store = StructureStore(tmp_path, root)
    revision = store.revision()
    if change == "order":
        root.write_text(json.dumps({"uid:2": "B", "uid:1": "A"}))
    elif change == "epoch":
        store.write_json(store.directory / "head.json", "new-epoch")
    user = SimpleNamespace(github_id="1")
    monkeypatch.setattr(project_utils, "get_user", lambda _id: user)
    monkeypatch.setattr(project_utils, "_schedule_file_commit", lambda *_args: "task")
    # Sorting has its own existing Root lookup; measure the validation reads here.
    monkeypatch.setattr(project_utils, "sort_data", lambda data, _path: data)
    monkeypatch.setattr(project_utils.search, "update_segments", lambda *_args: (True, None))
    monkeypatch.setattr(project_utils.search, "add_to_index", lambda *_args: (True, None))
    reads = []
    builtin_open, path_open = builtins.open, Path.open

    def track_open(path, *args, **kwargs):
        if Path(path) == root:
            reads.append(path)
        return builtin_open(path, *args, **kwargs)

    def track_path_open(path, *args, **kwargs):
        if path == root:
            reads.append(path)
        return path_open(path, *args, **kwargs)

    with monkeypatch.context() as tracking:
        tracking.setattr(builtins, "open", track_open)
        tracking.setattr(Path, "open", track_path_open)
        data = {"unknown" if change == "unknown_uid" else "uid:1": "saved"}
        if mode == "existing":
            result = project_utils.update_file(target, data, root, user, revision)
        else:
            virtual = VirtualProjectFile(source_path=root, source_muid="root-pli-ms",
                target_path=target, target_muid="translation-en-test", prefix="test")
            result = project_utils.materialize_translation_file(virtual, data, user, revision)
    assert len(reads) == 1
    if change:
        assert result[0] is False
        assert isinstance(result[1], KeyError if change == "unknown_uid" else StructureConflict)
        assert result[2] is None
        assert not target.exists() if mode == "virtual" else json.loads(target.read_text()) == original
    else:
        assert result[:3] == (True, None, "task")
        assert json.loads(target.read_text()) == {
            "uid:1": "saved", "uid:2": "" if mode == "virtual" else "kept"}


def _patch_file_in_process(path_string, key, value, start):
    path = Path(path_string)
    start.wait(timeout=2)
    with project_file_lock(path):
        data = json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.05)
        data[key] = value
        path.write_text(json.dumps(data), encoding="utf-8")


def test_update_file_preserves_concurrent_segment_patches(tmp_path, monkeypatch):
    monkeypatch.setattr(project_utils.settings, 'WORK_DIR', tmp_path)
    target_path = tmp_path / "translation.json"
    root_path = tmp_path / "root.json"
    target_path.write_text(json.dumps({"uid:1": "", "uid:2": ""}), encoding="utf-8")
    root_path.write_text(
        json.dumps({"uid:1": "source 1", "uid:2": "source 2"}),
        encoding="utf-8",
    )

    real_get_json_data = project_utils.get_json_data
    real_write_json_data = project_utils.write_json_data
    start = threading.Barrier(3)
    write_lock = threading.Lock()

    def delayed_read(path):
        data = real_get_json_data(path)
        if path == target_path:
            time.sleep(0.05)
        return data

    def serialized_write(path, data):
        with write_lock:
            return real_write_json_data(path, data)

    user = SimpleNamespace(
        github_id="1",
        username="tester",
        model_dump=lambda: {"github_id": "1", "username": "tester"},
    )
    monkeypatch.setattr(project_utils, "get_json_data", delayed_read)
    monkeypatch.setattr(project_utils, "write_json_data", serialized_write)
    monkeypatch.setattr(project_utils, "sort_data", lambda data, _path: data)
    monkeypatch.setattr(project_utils, "get_user", lambda _github_id: user)
    monkeypatch.setattr(
        project_utils.search,
        "update_segments",
        lambda _path, _data: (True, None),
    )
    monkeypatch.setattr(
        project_utils.commit,
        "delay",
        lambda *_args, **_kwargs: SimpleNamespace(id="task"),
    )

    def update(data):
        start.wait(timeout=2)
        return project_utils.update_file(target_path, data, root_path, user)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(update, {"uid:1": "first"}),
            pool.submit(update, {"uid:2": "second"}),
        ]
        start.wait(timeout=2)
        results = [future.result(timeout=2) for future in futures]

    assert all(updated and error is None for updated, error, _task_id in results)
    assert json.loads(target_path.read_text(encoding="utf-8")) == {
        "uid:1": "first",
        "uid:2": "second",
    }


def test_failed_materialization_does_not_delete_concurrent_successful_save(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(project_utils.settings, 'WORK_DIR', tmp_path)
    source_path = tmp_path / "root.json"
    target_path = tmp_path / "translation.json"
    source_path.write_text(
        json.dumps({"uid:1": "source 1", "uid:2": "source 2"}),
        encoding="utf-8",
    )
    virtual_file = VirtualProjectFile(
        source_path=source_path,
        source_muid="root-pli-ms",
        target_path=target_path,
        target_muid="translation-en-test",
        prefix="test",
    )
    user = SimpleNamespace(
        github_id="1",
        username="tester",
        model_dump=lambda: {"github_id": "1", "username": "tester"},
    )
    first_index_started = threading.Event()
    allow_first_index_to_fail = threading.Event()
    save_committed = threading.Event()
    add_to_index_calls = 0
    add_to_index_lock = threading.Lock()

    def add_to_index(_path):
        nonlocal add_to_index_calls
        with add_to_index_lock:
            add_to_index_calls += 1
            call_number = add_to_index_calls
        if call_number == 1:
            first_index_started.set()
            allow_first_index_to_fail.wait(timeout=2)
            return False, RuntimeError("forced indexing failure")
        return True, None

    def commit_save(*_args, **_kwargs):
        save_committed.set()
        return SimpleNamespace(id="task")

    monkeypatch.setattr(project_utils, "sort_data", lambda data, _path: data)
    monkeypatch.setattr(project_utils, "get_user", lambda _github_id: user)
    monkeypatch.setattr(project_utils.search, "add_to_index", add_to_index)
    monkeypatch.setattr(
        project_utils.search,
        "update_segments",
        lambda _path, _data: (True, None),
    )
    monkeypatch.setattr(
        project_utils.search,
        "remove_segments",
        lambda _path: (True, None),
    )
    monkeypatch.setattr(project_utils.commit, "delay", commit_save)

    results = {}

    def materialize(name, data):
        results[name] = project_utils.materialize_translation_file(
            virtual_file,
            data,
            user,
        )

    first = threading.Thread(
        target=materialize,
        args=("first", {"uid:1": "first"}),
    )
    second = threading.Thread(
        target=materialize,
        args=("second", {"uid:2": "second"}),
    )

    first.start()
    assert first_index_started.wait(timeout=2)
    second.start()
    save_committed.wait(timeout=0.2)
    allow_first_index_to_fail.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert results["first"][0] is False
    assert results["second"] == (True, None, "task", True)
    assert json.loads(target_path.read_text(encoding="utf-8")) == {
        "uid:1": "",
        "uid:2": "second",
    }


def test_project_file_lock_serializes_processes(tmp_path):
    target_path = tmp_path / "translation.json"
    target_path.write_text(json.dumps({"uid:1": "", "uid:2": ""}), encoding="utf-8")
    context = multiprocessing.get_context("fork")
    start = context.Event()
    processes = [
        context.Process(
            target=_patch_file_in_process,
            args=(str(target_path), "uid:1", "first", start),
        ),
        context.Process(
            target=_patch_file_in_process,
            args=(str(target_path), "uid:2", "second", start),
        ),
    ]

    try:
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(timeout=3)

        assert all(process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)

    assert json.loads(target_path.read_text(encoding="utf-8")) == {
        "uid:1": "first",
        "uid:2": "second",
    }


def test_write_json_data_preserves_original_when_serialization_fails(
    tmp_path, monkeypatch
):
    target_path = tmp_path / "translation.json"
    original = {"uid:1": "original"}
    target_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(project_utils, "sort_data", lambda data, _path: data)

    def fail_after_partial_write(_data, file, **_kwargs):
        file.write('{"uid:1": ')
        raise OSError("serialization failed")

    monkeypatch.setattr(project_utils.json, "dump", fail_after_partial_write)

    written, error = project_utils.write_json_data(target_path, {"uid:1": "new"})

    assert not written
    assert isinstance(error, OSError)
    assert json.loads(target_path.read_text(encoding="utf-8")) == original


def test_write_json_data_preserves_existing_file_permissions(tmp_path, monkeypatch):
    target_path = tmp_path / "translation.json"
    target_path.write_text(json.dumps({"uid:1": "original"}), encoding="utf-8")
    target_path.chmod(0o640)
    monkeypatch.setattr(project_utils, "sort_data", lambda data, _path: data)

    written, error = project_utils.write_json_data(target_path, {"uid:1": "new"})

    assert written
    assert error is None
    assert stat.S_IMODE(target_path.stat().st_mode) == 0o640
