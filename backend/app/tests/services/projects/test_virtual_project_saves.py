import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import tasks
from app.api.api_v1.endpoints import projects
from app.core.config import settings
from app.services.projects import utils as project_utils
from app.services.projects.file_coordinator import project_file_lock
from app.services.projects.virtual_projects import VirtualProjectFile


@pytest.fixture
def configured_translation(tmp_path, monkeypatch):
    work_dir = tmp_path / "unpublished"
    source = work_dir / "root/pli/ms/sutta/mn/mn1_root-pli-ms.json"
    target = work_dir / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"mn1:1": "Source 1", "mn1:2": "Source 2"}))
    (work_dir / "_project-v2.json").write_text(json.dumps([
        {
            "root_path": "root/pli/ms/sutta",
            "translation_path": "translation/en/tester/sutta",
            "translation_muids": "translation-en-tester",
        }
    ]))
    monkeypatch.setattr(settings, "WORK_DIR", work_dir)
    user = SimpleNamespace(github_id="1", username="tester", model_dump=lambda: {})
    monkeypatch.setattr(project_utils, "get_user", lambda _: user)
    monkeypatch.setattr(projects, "can_edit_translation", lambda *_: True)
    monkeypatch.setattr(
        project_utils.commit, "delay", lambda *_: SimpleNamespace(id="save-task")
    )
    monkeypatch.setattr(tasks.update_file_translation_progress, "delay", lambda *_: None)
    monkeypatch.setattr(project_utils.search, "add_to_index", lambda *_: (True, None))
    monkeypatch.setattr(projects.search, "add_to_index", lambda *_: (True, None))
    monkeypatch.setattr(project_utils.search, "update_segments", lambda *_: (True, None))
    virtual_file = VirtualProjectFile(
        source, "root-pli-ms", target, "translation-en-tester", "mn1"
    )
    return virtual_file, user


@pytest.mark.parametrize("translation_index_visible", [False, True])
def test_consecutive_saves_preserve_both_segments(
    configured_translation, monkeypatch, translation_index_visible
):
    virtual_file, user = configured_translation

    def indexed_paths(muid, prefix=None, exact=False, _type="root_path"):
        if muid == virtual_file.source_muid:
            return {str(virtual_file.source_path)}
        if translation_index_visible and virtual_file.target_path.exists():
            path = virtual_file.target_path if _type == "file_path" else virtual_file.source_path
            return {str(path)}
        return set()

    monkeypatch.setattr(projects.search, "get_file_paths", indexed_paths)
    for uid, value in [("mn1:1", "First"), ("mn1:2", "Second"), ("mn1:1", "")]:
        response = asyncio.run(projects.update_json_data_for_prefix_in_project(
            user, virtual_file.target_muid, virtual_file.prefix, {uid: value}
        ))
        assert response.materialized is True
        assert response.task_id == "save-task"
        contents = json.loads(virtual_file.target_path.read_text())
        assert contents[uid] == value
        if uid == "mn1:2":
            assert contents["mn1:1"] == "First"
    assert contents == {"mn1:1": "", "mn1:2": "Second"}


@pytest.mark.parametrize("data", [{}, {"mn1:1": ""}, {"mn1:1": " \t\n"}])
def test_blank_first_save_does_not_create_translation(configured_translation, data):
    virtual_file, user = configured_translation
    result = project_utils.materialize_translation_file(virtual_file, data, user)
    assert result == (True, None, None, False)
    assert not virtual_file.target_path.parent.exists()


def test_existing_translation_without_mapping_still_saves(configured_translation, monkeypatch):
    virtual_file, user = configured_translation
    (settings.WORK_DIR / "_project-v2.json").write_text("[]")
    virtual_file.target_path.parent.mkdir(parents=True)
    virtual_file.target_path.write_text(json.dumps({"mn1:1": "First", "mn1:2": ""}))

    def indexed_paths(muid, prefix=None, exact=False, _type="root_path"):
        path = virtual_file.target_path if _type == "file_path" else virtual_file.source_path
        return {str(path)}

    monkeypatch.setattr(projects.search, "get_file_paths", indexed_paths)
    response = asyncio.run(projects.update_json_data_for_prefix_in_project(
        user, virtual_file.target_muid, virtual_file.prefix, {"mn1:2": "Second"}
    ))
    assert response.materialized is True
    assert json.loads(virtual_file.target_path.read_text()) == {"mn1:1": "First", "mn1:2": "Second"}


def test_blank_save_waits_for_concurrent_materialization(configured_translation, monkeypatch):
    virtual_file, user = configured_translation
    started = threading.Event()
    lock_attempted = threading.Event()
    finished = threading.Event()

    @contextmanager
    def observed_lock(path):
        lock_attempted.set()
        started.set()
        with project_file_lock(path):
            yield

    monkeypatch.setattr(project_utils, "project_file_lock", observed_lock)

    def clear_segment():
        try:
            return project_utils.materialize_translation_file(
                virtual_file, {"mn1:1": ""}, user
            )
        finally:
            finished.set()
            started.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with project_file_lock(virtual_file.target_path):
            pending = pool.submit(clear_segment)
            assert started.wait(timeout=5)
            waiting_on_lock = lock_attempted.is_set() and not finished.is_set()
            virtual_file.target_path.parent.mkdir(parents=True)
            virtual_file.target_path.write_text(
                json.dumps({"mn1:1": "First", "mn1:2": "Second"})
            )
        result = pending.result(timeout=5)

    assert waiting_on_lock, "Blank saves must check existence under the file lock"
    assert result == (True, None, "save-task", True)
    assert json.loads(virtual_file.target_path.read_text()) == {"mn1:1": "", "mn1:2": "Second"}
