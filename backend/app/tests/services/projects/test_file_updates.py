import json
import multiprocessing
import stat
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from app.services.projects import utils as project_utils
from app.services.projects.file_coordinator import project_file_lock
from app.services.projects.virtual_projects import VirtualProjectFile


def _patch_file_in_process(path_string, key, value, start):
    path = Path(path_string)
    start.wait(timeout=2)
    with project_file_lock(path):
        data = json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.05)
        data[key] = value
        path.write_text(json.dumps(data), encoding="utf-8")


def test_update_file_preserves_concurrent_segment_patches(tmp_path, monkeypatch):
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
