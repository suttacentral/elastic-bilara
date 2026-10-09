import fcntl
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from kombu.exceptions import OperationalError

from app.api.api_v1.endpoints import publications as api
from app.core.config import settings
from app.main import app
from app.services.auth import utils as auth_utils
from app.services.publications.conversion import to_legacy
from app.services.publications.errors import PublicationError, PublicationStorageError
from app.services.publications.schema import PublicationUpdate
from app.services.publications.service import PublicationService
from app.services.publications import store as storage


@pytest.fixture
def publication_files(tmp_path, monkeypatch):
    work = tmp_path / "publication-checkout"
    work.mkdir()
    entries = [{
        "publication_number": "scpub1", "creator_uid": "alice", "creator_name": "Alice",
        "creator_github_handle": " Alice ", "translation_title": "Original",
        "root_lang_iso": "pli", "translation_lang_iso": "en", "text_uid": "dn",
        "creation_process": "From Pali", "text_description": "Description",
        "license_type": "Creative Commons Zero", "license_abbreviation": "CC0",
        "license_url": "https://example.test/license", "license_statement": "Original licence",
        "first_published": "2014", "editions_url": "https://example.test/current",
        "is_published": True, "custom_field": {"preserve": True}, "pitaka": "sutta",
    }]
    entries.append({**deepcopy(entries[0]), "publication_number": "scpub2", "creator_github_handle": "bob"})
    entries.append({**deepcopy(entries[0]), "publication_number": "scpub3", "creator_github_handle": ["carol", "ALICE"]})
    entries.append({**deepcopy(entries[0]), "publication_number": "scpub4", "creator_github_handle": "bob, alice"})
    entries.append({**deepcopy(entries[0]), "publication_number": "scpub5", "creator_github_handle": "malice"})
    legacy_base = {
        "publication_number": "scpub1", "author_uid": "alice", "author_name": "Alice",
        "author_github_handle": "alice", "translation_title": "Original",
        "translation_process": "From Pali", "translation_description": "Description",
        "license": {"license_type": "Creative Commons Zero", "license_abbreviation": "CC0",
                    "license_url": "https://example.test/license", "license_statement": "Original licence"},
        "edition": [{"edition_number": "1", "publication_date": "2014", "publisher": "SuttaCentral",
                     "publication_type": "website", "edition_url": "https://example.test/current"}],
    }
    legacy = {entry["publication_number"]: {**deepcopy(legacy_base), "publication_number": entry["publication_number"]} for entry in entries}
    legacy["scpub1"]["edition"] = [
        {"edition_number": "2", "publication_date": "2020", "publisher": "SuttaCentral",
         "publication_type": "website", "edition_url": "https://example.test/current"},
        {"edition_number": "1", "publication_date": "2014", "publisher": "Original publisher",
         "publication_type": "book", "number_of_volumes": "2",
         "edition_url": ["https://example.test/book", "https://example.test/ebook"]},
    ]
    legacy["scpub1"].pop("author_name")
    legacy["scpub1"].pop("author_github_handle")
    legacy["scpub1"]["author_uid"] = "alice-team"
    legacy["scpub1"]["collaborator"] = [
        {"collaborator_uid": "alice", "author_name": "Alice", "author_github_handle": "alice"},
        {"collaborator_uid": "bob", "author_name": "Bob", "author_github_handle": "bob"},
    ]
    legacy["scpub1"]["external_field"] = "keep"
    (work / storage.PUBLICATION_FILES[0]).write_text(json.dumps(entries), encoding="utf-8")
    (work / storage.PUBLICATION_FILES[1]).write_text(json.dumps(legacy), encoding="utf-8")
    monkeypatch.setattr(settings, "WORK_DIR", work)
    return work


@pytest.fixture
def requester(monkeypatch):
    user = SimpleNamespace(github_id=123, username="alice", role="writer", is_active=True)
    user.model_dump = lambda: {"github_id": user.github_id, "username": user.username, "role": user.role}
    monkeypatch.setattr(api, "get_user", lambda github_id: user)
    # A stale token username must not grant access under the wrong DB identity.
    app.dependency_overrides[auth_utils.get_current_user] = lambda: SimpleNamespace(github_id="123", username="bob")
    yield user
    app.dependency_overrides.pop(auth_utils.get_current_user, None)


def read_files(work):
    return tuple(json.loads((work / name).read_text()) for name in storage.PUBLICATION_FILES)


async def update(client, changes, number="scpub1", **selection):
    current = (await client.get(f"/publications/{number}")).json()
    return await client.patch(f"/publications/{number}", json={
        "revision": current["_revision"], "changes": changes, **selection,
    })


@pytest.mark.asyncio
async def test_writer_list_is_filtered_using_current_database_username(async_client, publication_files, requester):
    response = await async_client.get("/publications/")
    assert response.status_code == 200
    assert [e["publication_number"] for e in response.json()] == ["scpub1", "scpub3", "scpub4"]
    assert (await async_client.get("/publications/scpub2")).status_code == 404
    assert (await async_client.get("/publications/missing")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("role,active", [("reviewer", True), ("writer", False), ("administrator", False)])
async def test_inactive_or_reviewer_rejected(async_client, publication_files, requester, role, active):
    requester.role, requester.is_active = role, active
    assert (await async_client.get("/publications/")).status_code == 403
    assert (await async_client.patch("/publications/scpub1", json={"revision": "old", "changes": {}})).status_code == 403


@pytest.mark.asyncio
async def test_authentication_required(async_client, publication_files):
    assert (await async_client.get("/publications/")).status_code == 401


@pytest.mark.asyncio
async def test_writer_cannot_forge_ownership_or_call_admin_operations(async_client, publication_files, requester):
    before = read_files(publication_files)
    for field, value in (("creator_github_handle", "alice"), ("publication_number", "scpub2"),
                         ("is_published", False), ("creator_uid", "bob"), ("source_url", "other")):
        response = await update(async_client, {field: value})
        assert response.status_code == 403
    for method, path, kwargs in (
        ("post", "/publications/", {"json": {"publication_number": "scpub10"}}),
        ("post", "/publications/publish/", {}),
        ("get", "/publications/next-number/", {}),
        ("delete", "/publications/scpub1", {"headers": {"If-Match": "old"}}),
    ):
        assert (await getattr(async_client, method)(path, **kwargs)).status_code == 403
    assert (await async_client.patch("/publications/scpub2", json={
        "revision": "anything", "changes": {"translation_title": "hack"},
    })).status_code == 404
    assert read_files(publication_files) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"If-Match": "old"}])
async def test_put_is_removed_without_changing_files(async_client, publication_files, requester, headers):
    requester.role = "administrator"
    before = read_files(publication_files)
    response = await async_client.put("/publications/scpub1", headers=headers, json={
        "publication_number": "scpub1", "translation_title": "Old client update",
    })
    assert response.status_code == 405
    assert read_files(publication_files) == before


def test_publish_service_rejects_writer_before_storage_access(publication_files, requester, monkeypatch):
    service = PublicationService(publication_files, requester)
    locked = Mock()
    monkeypatch.setattr(service.store, "locked", locked)
    with pytest.raises(PublicationError) as raised:
        service.check_publish()
    assert raised.value.status == 403
    locked.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("invalid_json", 409), ("invalid_structure", 409), ("missing_file", 503)])
async def test_publish_storage_failure_never_queues_task(async_client, publication_files, requester, monkeypatch, failure, status):
    requester.role = "administrator"
    task = Mock()
    monkeypatch.setattr(api.commit_task, "delay", task)
    path = publication_files / storage.PUBLICATION_FILES[0]
    if failure == "missing_file":
        path.unlink()
    else:
        path.write_text("{" if failure == "invalid_json" else "{}")
    response = await async_client.post("/publications/publish/")
    assert response.status_code == status
    if status == 503:
        assert 'storage is unavailable' in response.json()['detail']
    task.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('error_type', [OSError, OperationalError])
async def test_publish_queue_failure_is_not_reported_as_storage_failure(async_client, publication_files, requester, monkeypatch, error_type):
    requester.role = 'administrator'
    before = read_files(publication_files)
    task = Mock(side_effect=error_type('broker unavailable'))
    monkeypatch.setattr(api.commit_task, 'delay', task)
    response = await async_client.post('/publications/publish/')
    assert response.status_code == 503
    assert response.json()['detail'] == 'Publication task submission failed. Please retry publishing later.'
    task.assert_called_once()
    assert read_files(publication_files) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('failure_site', ['user_lookup', 'locked_service_body'])
async def test_non_storage_oserror_is_not_reclassified(async_client, publication_files, requester, monkeypatch, failure_site):
    error = OSError('not a publication storage failure')
    if failure_site == 'user_lookup':
        monkeypatch.setattr(api, 'get_user', Mock(side_effect=error))
    else:
        # owns() runs inside the read lock, but is not a storage operation.
        monkeypatch.setattr(PublicationService, 'owns', Mock(side_effect=error))
    with pytest.raises(OSError) as raised:
        await async_client.get('/publications/')
    assert raised.value is error


@pytest.mark.asyncio
async def test_publish_recovers_both_files_and_releases_lock_before_queueing(async_client, publication_files, requester, monkeypatch):
    requester.role = "administrator"
    v2, legacy = read_files(publication_files)
    v2[0]["translation_title"] = legacy["scpub1"]["translation_title"] = "Recovered"
    store = storage.PublicationStore(publication_files)
    store.directory.mkdir(parents=True)
    storage.write_json(store.journal, dict(zip(storage.PUBLICATION_FILES, (v2, legacy))))
    # Simulate a crash after only the first file was replaced.
    storage.write_json(publication_files / storage.PUBLICATION_FILES[0], v2)

    def queue(*args, **kwargs):
        assert read_files(publication_files) == (v2, legacy)
        assert json.loads(store.journal.read_text()) is None
        with (store.directory / "lock").open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
        return SimpleNamespace(id="recovered-task")

    task = Mock(side_effect=queue)
    monkeypatch.setattr(api.commit_task, "delay", task)
    response = await async_client.post("/publications/publish/")
    assert response.status_code == 202
    assert response.json()["task_id"] == "recovered-task"
    task.assert_called_once_with(requester.model_dump(), list(storage.PUBLICATION_FILES), "Update publication metadata", add=True)


@pytest.mark.asyncio
async def test_save_updates_both_formats_preserving_history_and_extra_fields(async_client, publication_files, requester):
    before_v2, before_legacy = read_files(publication_files)
    response = await update(async_client, {
        "translation_title": "新标题", "creation_process": "Revised process",
        "text_description": "Revised description", "license_statement": "Revised licence",
    })
    assert response.status_code == 200, response.text
    v2, legacy = read_files(publication_files)
    assert v2[0]["translation_title"] == legacy["scpub1"]["translation_title"] == "新标题"
    assert legacy["scpub1"]["translation_process"] == "Revised process"
    assert legacy["scpub1"]["translation_description"] == "Revised description"
    assert legacy["scpub1"]["license"]["license_statement"] == "Revised licence"
    for field in ("edition", "collaborator", "author_uid", "external_field"):
        assert legacy["scpub1"][field] == before_legacy["scpub1"][field]
    assert v2[0]["custom_field"] == before_v2[0]["custom_field"]
    assert v2[1:] == before_v2[1:]
    assert {k: v for k, v in legacy.items() if k != "scpub1"} == {k: v for k, v in before_legacy.items() if k != "scpub1"}
    assert (await async_client.get("/publications/scpub1")).json()["translation_title"] == "新标题"
    assert "_revision" not in v2[0]


@pytest.mark.asyncio
async def test_stale_same_record_rejected_but_other_records_can_save(async_client, publication_files, requester):
    first = (await async_client.get("/publications/scpub1")).json()
    other = (await async_client.get("/publications/scpub3")).json()
    assert (await update(async_client, {"translation_title": "First change"})).status_code == 200
    stale = await async_client.patch("/publications/scpub1", json={"revision": first["_revision"], "changes": {"translation_title": "Stale change"}})
    assert stale.status_code == 409
    assert (await async_client.patch("/publications/scpub3", json={"revision": other["_revision"], "changes": {"translation_title": "Other change"}})).status_code == 200
    v2, legacy = read_files(publication_files)
    assert v2[0]["translation_title"] == "First change"
    assert v2[2]["translation_title"] == "Other change"
    # Legacy-only changes preserve history without invalidating a v2 revision.
    original = (await async_client.get("/publications/scpub1")).json()
    legacy["scpub1"]["edition"][0]["publisher"] = "Changed elsewhere"
    (publication_files / storage.PUBLICATION_FILES[1]).write_text(json.dumps(legacy))
    assert (await async_client.patch("/publications/scpub1", json={"revision": original["_revision"], "changes": {}})).status_code == 200
    assert read_files(publication_files)[1]["scpub1"]["edition"][0]["publisher"] == "Changed elsewhere"


@pytest.mark.asyncio
async def test_ownership_rechecked_at_save(async_client, publication_files, requester):
    current = (await async_client.get("/publications/scpub1")).json()
    v2, _ = read_files(publication_files)
    v2[0]["creator_github_handle"] = "bob"
    (publication_files / storage.PUBLICATION_FILES[0]).write_text(json.dumps(v2))
    assert (await async_client.patch("/publications/scpub1", json={"revision": current["_revision"], "changes": {"translation_title": "No"}})).status_code == 404


@pytest.mark.asyncio
async def test_creator_name_updates_only_matching_collaborator(async_client, publication_files, requester):
    response = await update(async_client, {"creator_name": "Alice Updated"})
    assert response.status_code == 200, response.text
    _, legacy = read_files(publication_files)
    assert legacy["scpub1"]["collaborator"][0]["author_name"] == "Alice Updated"
    assert legacy["scpub1"]["collaborator"][1]["author_name"] == "Bob"
    assert legacy["scpub1"]["author_uid"] == "alice-team"


@pytest.mark.asyncio
async def test_legacy_date_alias_and_false_values_survive_other_edits(async_client, publication_files, requester):
    v2, legacy = read_files(publication_files)
    v2[2]["publication_date"] = v2[2].pop("first_published")
    v2[2]["translation_lang_iso"] = False
    v2[2]["license_abbreviation"] = False
    legacy["scpub3"]["edition"][0]["url"] = legacy["scpub3"]["edition"][0].pop("edition_url")
    for name, contents in zip(storage.PUBLICATION_FILES, (v2, legacy)):
        (publication_files / name).write_text(json.dumps(contents))
    assert (await update(async_client, {"translation_title": "New"}, number="scpub3")).status_code == 200
    assert read_files(publication_files)[0][2]["translation_lang_iso"] is False
    response = await update(async_client, {"first_published": "2012", "editions_url": "https://example.test/changed"}, number="scpub3")
    assert response.status_code == 200, response.text
    v2, legacy = read_files(publication_files)
    assert v2[2]["first_published"] == v2[2]["publication_date"] == "2012"
    assert legacy["scpub3"]["edition"][0]["publication_date"] == "2012"
    assert "url" not in legacy["scpub3"]["edition"][0]


@pytest.mark.asyncio
async def test_missing_legacy_record_is_generated(async_client, publication_files, requester):
    _, legacy = read_files(publication_files)
    del legacy["scpub1"]
    (publication_files / storage.PUBLICATION_FILES[1]).write_text(json.dumps(legacy))
    response = await update(async_client, {"translation_title": "Created legacy"})
    assert response.status_code == 200, response.text
    _, legacy = read_files(publication_files)
    assert legacy["scpub1"]["author_uid"] == "alice"
    assert legacy["scpub1"]["edition"][0]["publication_date"] == "2014"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["administrator", "superuser"])
async def test_admin_create_rename_delete_and_publish_both_files(async_client, publication_files, requester, monkeypatch, role):
    requester.role = role
    assert len((await async_client.get("/publications/")).json()) == 5
    assert (await async_client.get("/publications/next-number/")).json()["next_number"] == "scpub6"
    created = await async_client.post("/publications/", json={"publication_number": "scpub6", "creator_uid": "new", "creator_name": "New", "creator_github_handle": "new"})
    assert created.status_code == 201, created.text
    assert "scpub6" in read_files(publication_files)[1]
    assert (await async_client.post("/publications/", json={"publication_number": "scpub6", "creator_uid": "new"})).status_code == 409
    renamed = await update(async_client, {"publication_number": "scpub7"}, number="scpub6")
    assert renamed.status_code == 200
    assert "scpub6" not in read_files(publication_files)[1]
    assert (await async_client.delete("/publications/scpub7", headers={"If-Match": renamed.json()["_revision"]})).status_code == 200
    assert "scpub7" not in read_files(publication_files)[1]
    task = Mock(return_value=SimpleNamespace(id="queued-task"))
    monkeypatch.setattr(api.commit_task, "delay", task)
    response = await async_client.post("/publications/publish/")
    assert response.status_code == 202
    assert task.call_args.args[1] == list(storage.PUBLICATION_FILES)


@pytest.mark.asyncio
async def test_invalid_payload_never_writes(async_client, publication_files, requester):
    before = read_files(publication_files)
    for changes in ({"unknown": "x"}, {"translation_title": None}, {"creator_name": 123}, {"creator_name": ["Alice", "Injected"]}):
        assert (await update(async_client, changes)).status_code == 422
    assert (await async_client.patch("/publications/scpub1", json={"changes": {"translation_title": "No revision"}})).status_code == 422
    assert read_files(publication_files) == before


def test_interrupted_two_file_save_is_recovered_before_next_read(publication_files, requester, monkeypatch):
    service = PublicationService(publication_files, requester)
    initial = service.get("scpub1")
    original_replace = storage.os.replace
    failed = False

    def fail_once(source, path):
        nonlocal failed
        if path.name == "_publication.json" and not failed:
            failed = True
            raise OSError("simulated disk failure")
        original_replace(source, path)

    monkeypatch.setattr(storage.os, "replace", fail_once)
    with pytest.raises(PublicationStorageError) as raised:
        service.update("scpub1", PublicationUpdate(revision=initial["_revision"], changes={"translation_title": "Durable change"}))
    assert isinstance(raised.value.__cause__, OSError)
    assert json.loads(service.store.journal.read_text()) is not None
    assert PublicationService(publication_files, requester).get("scpub1")["translation_title"] == "Durable change"
    v2, legacy = read_files(publication_files)
    assert v2[0]["translation_title"] == legacy["scpub1"]["translation_title"] == "Durable change"
    assert json.loads(service.store.journal.read_text()) is None


def test_parallel_updates_do_not_overwrite_different_records(publication_files, requester):
    from concurrent.futures import ThreadPoolExecutor

    service = PublicationService(publication_files, requester)
    records = [service.get(number) for number in ("scpub1", "scpub3")]
    def save(record):
        other = PublicationService(publication_files, requester)
        return other.update(record["publication_number"], PublicationUpdate(
            revision=record["_revision"], changes={"translation_title": record["publication_number"]},
        ))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, records))
    assert len(results) == 2
    v2, legacy = read_files(publication_files)
    for index in (0, 2):
        assert v2[index]["translation_title"] == v2[index]["publication_number"]
        assert legacy[v2[index]["publication_number"]]["translation_title"] == v2[index]["publication_number"]


@pytest.mark.asyncio
async def test_creation_rejects_conflicting_date_aliases(async_client, publication_files, requester):
    requester.role = "administrator"
    before = read_files(publication_files)
    response = await async_client.post("/publications/", json={
        "publication_number": "scpub6", "creator_uid": "alice",
        "first_published": "2014", "publication_date": "2020",
    })
    assert response.status_code == 422
    assert read_files(publication_files) == before


@pytest.mark.asyncio
async def test_invalid_and_duplicate_files_fail_without_replacing_them(async_client, publication_files, requester):
    path = publication_files / storage.PUBLICATION_FILES[0]
    v2, _ = read_files(publication_files)
    path.write_text(json.dumps(v2 + [v2[0]]))
    assert (await async_client.get("/publications/")).status_code == 409
    path.write_text("{broken json")
    assert (await async_client.get("/publications/")).status_code == 409
    assert path.read_text() == "{broken json"


def _locked_reader(work, started, finished):
    started.set()
    with storage.PublicationStore(work).locked():
        finished.set()


def test_store_lock_excludes_other_processes_and_allows_nested_git_operations(publication_files):
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    started, finished = context.Event(), context.Event()
    process = context.Process(target=_locked_reader, args=(publication_files, started, finished))
    with storage.PublicationStore(publication_files).locked():
        with storage.PublicationStore(publication_files).locked():
            process.start()
            assert started.wait(15)
            assert not finished.wait(0.1)
    process.join(15)
    if process.is_alive():
        process.terminate()
        process.join()
        pytest.fail("Publication lock was not released")
    assert process.exitcode == 0
    assert finished.is_set()


@pytest.mark.asyncio
async def test_historical_v2_fields_survive_save(async_client, publication_files, requester):
    v2, legacy = read_files(publication_files)
    historical = {'edition_number': '4', 'publisher': 'Historical publisher', 'publication_type': 'book', 'publication_date': '2014'}
    v2[0].update(historical)
    (publication_files / storage.PUBLICATION_FILES[0]).write_text(json.dumps(v2))
    response = await update(async_client, {'translation_title': 'Edited'})
    assert response.status_code == 200, response.text
    saved_v2, saved_legacy = read_files(publication_files)
    assert all(saved_v2[0][key] == value for key, value in historical.items())
    assert saved_legacy['scpub1']['edition'] == legacy['scpub1']['edition']
    assert saved_legacy['scpub1']['author_uid'] == 'alice-team'


@pytest.mark.asyncio
async def test_v2_dates_and_urls_save_without_legacy_selectors(async_client, publication_files, requester):
    _, before = read_files(publication_files)
    response = await update(async_client, {'first_published': '2013', 'editions_url': 'https://example.test/new'})
    assert response.status_code == 200, response.text
    v2, legacy = read_files(publication_files)
    assert v2[0]['first_published'] == '2013'
    assert v2[0]['editions_url'] == 'https://example.test/new'
    assert legacy['scpub1']['edition'] == before['scpub1']['edition']
    assert set(response.json()) == set(v2[0]) | {'_revision'}


@pytest.mark.asyncio
@pytest.mark.parametrize('legacy_content', ['{broken', '{}'])
async def test_reads_and_numbering_use_only_v2(async_client, publication_files, requester, legacy_content):
    requester.role = 'administrator'
    (publication_files / storage.PUBLICATION_FILES[1]).write_text(legacy_content)
    assert len((await async_client.get('/publications/')).json()) == 5
    assert (await async_client.get('/publications/scpub1')).status_code == 200
    assert (await async_client.get('/publications/next-number/')).json()['next_number'] == 'scpub6'
    if legacy_content == '{broken':
        before = (publication_files / storage.PUBLICATION_FILES[0]).read_bytes()
        assert (await update(async_client, {'translation_title': 'No destructive repair'})).status_code == 409
        assert (publication_files / storage.PUBLICATION_FILES[0]).read_bytes() == before
        assert (publication_files / storage.PUBLICATION_FILES[1]).read_text() == legacy_content


@pytest.mark.asyncio
async def test_numbering_ignores_legacy_only_records_and_preserves_them(async_client, publication_files, requester):
    requester.role = 'administrator'
    _, legacy = read_files(publication_files)
    legacy['scpub900'] = {'publication_number': 'scpub900', 'archive': True}
    storage.write_json(publication_files / storage.PUBLICATION_FILES[1], legacy)
    assert (await async_client.get('/publications/next-number/')).json()['next_number'] == 'scpub6'
    assert (await update(async_client, {'translation_title': 'Updated'})).status_code == 200
    assert read_files(publication_files)[1]['scpub900'] == legacy['scpub900']
    before = read_files(publication_files)
    assert (await update(async_client, {'publication_number': 'scpub900'})).status_code == 409
    assert read_files(publication_files) == before


@pytest.mark.asyncio
async def test_create_rejects_suggested_number_with_legacy_history(async_client, publication_files, requester):
    requester.role = 'administrator'
    _, legacy = read_files(publication_files)
    legacy['scpub6'] = {
        'publication_number': 'scpub6', 'author_uid': 'previous-author',
        'author_name': 'Previous Author',
        'edition': [{'edition_number': '3', 'publication_date': '1900', 'publisher': 'Historical publisher'}],
        'archive': {'preserve': True},
    }
    storage.write_json(publication_files / storage.PUBLICATION_FILES[1], legacy)
    number = (await async_client.get('/publications/next-number/')).json()['next_number']
    assert number == 'scpub6'
    before = [(publication_files / name).read_bytes() for name in storage.PUBLICATION_FILES]
    body = {'publication_number': number, 'creator_uid': 'new-author', 'creator_name': 'New Author'}
    response = await async_client.post('/publications/', json=body)
    assert response.status_code == 409
    assert 'compatibility history' in response.json()['detail']
    assert [(publication_files / name).read_bytes() for name in storage.PUBLICATION_FILES] == before

    response = await async_client.post('/publications/', json={**body, 'publication_number': 'scpub7'})
    assert response.status_code == 201, response.text
    v2, saved_legacy = read_files(publication_files)
    assert not any(entry['publication_number'] == 'scpub6' for entry in v2)
    assert saved_legacy['scpub6'] == legacy['scpub6']
    assert saved_legacy['scpub7']['author_uid'] == 'new-author'
    assert saved_legacy['scpub7']['edition'][0]['publisher'] == 'SuttaCentral'
    assert 'archive' not in saved_legacy['scpub7']


@pytest.mark.asyncio
@pytest.mark.parametrize('handles', ['alice', ['alice'], ['alice', 'editor', 'other'], False])
async def test_team_author_edits_are_independent_of_editing_accounts(async_client, publication_files, requester, handles):
    requester.role = 'administrator'
    v2, legacy = read_files(publication_files)
    v2[0].update(creator_uid=['alice', 'bob'], creator_name=['Alice', 'Bob'], creator_github_handle=handles)
    legacy['scpub1']['collaborator'][0]['credit'] = {'role': 'translator'}
    for name, value in zip(storage.PUBLICATION_FILES, (v2, legacy)):
        storage.write_json(publication_files / name, value)
    response = await update(async_client, {'creator_uid': ['bob', 'carol'], 'creator_name': ['Bob Updated', 'Carol']})
    assert response.status_code == 200, response.text
    saved, old = read_files(publication_files)
    assert saved[0]['creator_uid'] == ['bob', 'carol']
    assert saved[0]['creator_name'] == ['Bob Updated', 'Carol']
    assert saved[0]['creator_github_handle'] == handles
    assert old['scpub1']['collaborator'][0] == legacy['scpub1']['collaborator'][0]
    assert old['scpub1']['collaborator'][1]['author_name'] == 'Bob Updated'
    response = await update(async_client, {'creator_uid': 'carol', 'creator_name': 'Carol'})
    assert response.status_code == 200, response.text
    assert read_files(publication_files)[0][0]['creator_github_handle'] == handles


@pytest.mark.asyncio
async def test_changing_editing_accounts_does_not_guess_legacy_author_handles(async_client, publication_files, requester):
    requester.role = 'administrator'
    _, before = read_files(publication_files)
    response = await update(async_client, {'creator_github_handle': ['new-editor']})
    assert response.status_code == 200, response.text
    v2, legacy = read_files(publication_files)
    assert v2[0]['creator_github_handle'] == ['new-editor']
    assert legacy['scpub1']['collaborator'] == before['scpub1']['collaborator']
    requester.role, requester.username = 'writer', 'new-editor'
    assert (await async_client.get('/publications/scpub1')).status_code == 200
    requester.username = 'bob'
    assert (await async_client.get('/publications/scpub1')).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('creator', [
    {'creator_uid': ['alice', 'bob'], 'creator_name': ['Alice', 'Bob'], 'creator_github_handle': 'editor'},
    {'creator_uid': 'foundation', 'creator_name': 'A foundation', 'creator_github_handle': False},
])
async def test_create_uses_v2_metadata_without_legacy_options(async_client, publication_files, requester, creator):
    requester.role = 'administrator'
    body = {'publication_number': 'scpub6', **creator}
    response = await async_client.post('/publications/', json=body)
    assert response.status_code == 201, response.text
    v2, legacy = read_files(publication_files)
    assert v2[-1] == body
    assert legacy['scpub6']['edition'][0]['publisher'] == 'SuttaCentral'
    if isinstance(creator['creator_uid'], list):
        assert legacy['scpub6']['author_uid'] == 'scpub6'
        assert [c['collaborator_uid'] for c in legacy['scpub6']['collaborator']] == ['alice', 'bob']
        assert all(c['author_github_handle'] == '' for c in legacy['scpub6']['collaborator'])
    else:
        assert legacy['scpub6']['author_uid'] == 'foundation'


@pytest.mark.asyncio
@pytest.mark.parametrize('creator', [{}, {'creator_uid': ''}, {'creator_uid': ' \t'},
                                    {'creator_uid': False}, {'creator_uid': None},
                                    {'creator_uid': [], 'creator_name': []},
                                    {'creator_uid': [' '], 'creator_name': ['Nobody']}])
async def test_create_requires_creator_uid_without_writing_files(async_client, publication_files, requester, creator):
    requester.role = 'administrator'
    before = [(publication_files / name).read_bytes() for name in storage.PUBLICATION_FILES]
    response = await async_client.post('/publications/', json={'publication_number': 'scpub6', **creator})
    assert response.status_code == 422
    assert [(publication_files / name).read_bytes() for name in storage.PUBLICATION_FILES] == before


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [
    {'creator_uid': [], 'creator_name': []},
    {'creator_uid': ['alice', 'alice'], 'creator_name': ['Alice', 'Other']},
    {'creator_uid': ['alice', 'bob'], 'creator_name': ['Alice']},
    {'creator_uid': [' '], 'creator_name': ['Nobody']},
    {'creator_uid': 'alice', 'creator_name': ['Alice']},
])
async def test_invalid_v2_author_structure_never_writes(async_client, publication_files, requester, changes):
    requester.role = 'administrator'
    before = read_files(publication_files)
    assert (await update(async_client, changes)).status_code == 422
    assert read_files(publication_files) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('extra', [
    {'legacy': {'author_uid': 'team'}}, {'first_published_edition': 1},
    {'editions_url_edition': 0}, {'editions_url_item': 0},
])
async def test_removed_conversion_options_are_rejected(async_client, publication_files, requester, extra):
    requester.role = 'administrator'
    before = read_files(publication_files)
    assert (await update(async_client, {}, **extra)).status_code == 422
    assert (await async_client.post('/publications/', json={'publication_number': 'scpub6', **extra})).status_code == 422
    assert read_files(publication_files) == before


def test_converter_preserves_ambiguous_history_and_extensions():
    entry = {'publication_number': 'scpub6', 'creator_uid': ['alice', 'bob'],
             'creator_name': ['Alice Updated', 'Bob Updated'], 'creator_github_handle': 'editor',
             'first_published': '2026', 'editions_url': 'new', 'license_statement': 'Updated'}
    legacy = {'author_uid': 'old-team', 'collaborator': [
        {'collaborator_uid': '', 'author_name': 'Alice', 'credit': 'Original'},
        {'collaborator_uid': 'bob', 'author_name': 'Bob'},
        {'collaborator_uid': 'bob', 'author_name': 'Another Bob'},
    ], 'edition': [{'publication_date': '2000', 'edition_url': ['book', 'ebook'], 'custom': True}],
        'license': {'custom': 'keep'}, 'custom': {'keep': True}}
    before = deepcopy(legacy)
    converted = to_legacy(entry, legacy)
    assert legacy == before
    assert converted['collaborator'] == legacy['collaborator']
    assert converted['edition'][0]['edition_url'] == ['book', 'ebook']
    assert converted['edition'][0]['publication_date'] == '2026'
    assert converted['edition'][0]['custom'] is True
    assert converted['license'] == {'custom': 'keep', 'license_statement': 'Updated'}
    assert converted['custom'] == legacy['custom']


@pytest.mark.asyncio
async def test_real_author_shapes_save_all_v2_names_without_granting_legacy_access(async_client, publication_files, requester):
    from pathlib import Path

    fixtures = json.loads((Path(__file__).parent / 'fixtures/publication_authors.json').read_text())
    entries = [case['v2'] for case in fixtures]
    legacy = {case['v2']['publication_number']: case['legacy'] for case in fixtures}
    for name, value in zip(storage.PUBLICATION_FILES, (entries, legacy)):
        storage.write_json(publication_files / name, value)
    requester.role = 'administrator'
    for entry in entries:
        number = entry['publication_number']
        names = entry['creator_name']
        updated = [name + ' Updated' for name in names] if isinstance(names, list) else names + ' Updated'
        response = await update(async_client, {'creator_name': updated}, number=number)
        assert response.status_code == 200, (number, response.text)
        assert response.json()['creator_name'] == updated
        assert response.json()['creator_uid'] == entry['creator_uid']
        assert response.json()['creator_github_handle'] == entry['creator_github_handle']
        assert not any(key.startswith('_legacy') for key in response.json())
    requester.role = 'writer'
    for number, account in [('scpub24', 'alexwynne'), ('scpub24', 'kovilo'), ('scpub26', 'ashinsarana')]:
        requester.username = account
        assert (await async_client.get(f'/publications/{number}')).status_code == 404
    requester.username = 'sujato'
    for number in ['scpub22', 'scpub23']:
        assert (await async_client.get(f'/publications/{number}')).status_code == 200
