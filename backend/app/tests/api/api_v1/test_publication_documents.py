"""Document APIs use temporary checkouts; task dispatch never contacts a broker."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pygit2
import pytest

from app import tasks
from app.api.api_v1.endpoints import publication_documents as api
from app.core.config import settings
from app.main import app
from app.services.auth import utils as auth_utils
from app.services.publication_documents.catalog import document_id
from app.services.publication_documents.store import DocumentStore, revision

PATH = '_publication/en/alice/editions/dn/matter/introduction.html'
SECOND = '_publication/en/alice/editions/dn/matter/preface.html'
OTHER = '_publication/en/bob/editions/mn/matter/introduction.html'
HTML = "<article>\r\n<h1 id='intro'>Introduction</h1>\r\n<p lang='pli' translate='no'>Ānanda <a epub:type='noteref' role='doc-noteref' href='#note'>1</a></p>\r\n<aside id='note'>Note</aside>\r\n</article>\r\n"


def commit_repo(repo):
    repo.index.add_all(); repo.index.write()
    signature = pygit2.Signature('Fixture', 'fixture@example.org')
    return repo.create_commit('HEAD', signature, signature, 'fixture', repo.index.write_tree(),
                              [] if repo.head_is_unborn else [repo.head.target])


@pytest.fixture
def documents(tmp_path, monkeypatch):
    work = tmp_path / 'document-checkouts' / 'unpublished'
    published = tmp_path / 'document-checkouts' / 'published'
    for directory, branch in ((work, 'unpublished'), (published, 'published')):
        repo = pygit2.init_repository(str(directory), initial_head=branch)
        entries = [{'publication_number': 'scpub1', 'creator_github_handle': 'alice', 'translation_title': 'Long Discourses'},
                   {'publication_number': 'scpub2', 'creator_github_handle': 'bob', 'translation_title': 'Middle Discourses'}]
        (directory / '_publication-v2.json').write_text(json.dumps(entries))
        for path in (PATH, SECOND, OTHER):
            target = directory / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(HTML.encode('utf-8'))
        for path, number in ((PATH, 'scpub1'), (OTHER, 'scpub2')):
            folder = (directory / path).parent.parent
            for edition in ('web', 'epub'):
                (folder / f'{edition}.json').write_text(json.dumps({'publication_number': number,
                    'edition_number': edition, 'publication_type': edition,
                    'volumes': [{'frontmatter': ['./matter/introduction.html'] + (['./matter/preface.html'] if number == 'scpub1' else [])}]}))
        commit_repo(repo)
    monkeypatch.setattr(settings, 'WORK_DIR', work)
    monkeypatch.setattr(settings, 'PUBLISHED_DIR', published)
    queue = Mock()
    monkeypatch.setattr(tasks.process_publication_documents, 'apply_async', queue)
    user = SimpleNamespace(github_id=123, username='alice', email='alice@example.org', avatar_url=None, role='writer', is_active=True)
    user.model_dump = lambda: {key: value for key, value in vars(user).items() if key != 'model_dump'}
    monkeypatch.setattr(api, 'get_user', lambda _: user)
    app.dependency_overrides[auth_utils.get_current_user] = lambda: SimpleNamespace(github_id='123', username='forged')
    yield SimpleNamespace(work=work, published=published, user=user, queue=queue, uid=document_id(PATH), second=document_id(SECOND))
    app.dependency_overrides.pop(auth_utils.get_current_user, None)


def endpoint(uid, suffix=''):
    return f'/publication-documents/scpub1/documents/{uid}{suffix}'


async def save(client, documents, content, uid=None):
    url = endpoint(uid or documents.uid)
    detail = (await client.get(url)).json()
    return await client.put(url, json={'content': content, 'revision': detail['revision'], 'published_revision': detail['published_revision']})


@pytest.mark.asyncio
@pytest.mark.parametrize('filenames', [
    ['introduction.html', 'preface.html'],
    ['preface.html', 'introduction.html'],
])
async def test_catalog_preserves_order_deduplicates_editions_and_filters_current_owner(async_client, documents, filenames):
    folder = (documents.work / PATH).parent.parent
    # The first configuration in path order determines each document's position.
    for edition, names in [('epub', filenames), ('web', list(reversed(filenames)))]:
        config = folder / f'{edition}.json'
        entry = json.loads(config.read_text())
        entry['volumes'] = [{'frontmatter': [f'./matter/{name}' for name in names + names[:1]]}]
        config.write_text(json.dumps(entry))
    counts = await async_client.get('/publication-documents/counts/')
    assert counts.json() == {'scpub1': 2}
    response = await async_client.get('/publication-documents/scpub1/')
    assert response.status_code == 200
    assert [doc['filename'] for doc in response.json()['documents']] == filenames
    assert all(len(doc['editions']) == 2 for doc in response.json()['documents'])
    assert response.headers['cache-control'] == 'no-store'
    assert (await async_client.get('/publication-documents/scpub2/')).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('role,active', [('reviewer', True), ('writer', False), ('administrator', False)])
async def test_document_permissions_are_enforced_on_server(async_client, documents, role, active):
    documents.user.role, documents.user.is_active = role, active
    assert (await async_client.get(endpoint(documents.uid))).status_code == 403
    assert (await async_client.get('/publication-documents/scpub1/status/')).status_code == 403


@pytest.mark.asyncio
async def test_detail_and_noop_save_preserve_every_byte_and_do_not_queue(async_client, documents):
    result = await save(async_client, documents, HTML)
    assert result.status_code == 200
    assert result.json()['validation']['valid']
    assert result.json()['content'] == HTML
    assert (documents.work / PATH).read_bytes() == HTML.encode('utf-8')
    documents.queue.assert_not_called()


@pytest.mark.asyncio
async def test_save_only_changes_selected_file_and_queues_durable_intent(async_client, documents):
    edited = HTML.replace('Ānanda', 'Ānanda and Sāriputta')
    result = await save(async_client, documents, edited)
    assert result.status_code == 200
    assert (documents.work / PATH).read_bytes() == edited.encode('utf-8')
    assert (documents.work / SECOND).read_bytes() == HTML.encode('utf-8')
    assert (documents.published / PATH).read_bytes() == HTML.encode('utf-8')
    state = DocumentStore(documents.work, 'scpub1').read()
    assert list(state['sync']['documents']) == [documents.uid]
    assert state['sync']['status'] == 'queued'
    documents.queue.assert_called_once()
    assert documents.queue.call_args.args[0][1:] == ('scpub1', 'sync')


@pytest.mark.asyncio
async def test_stale_save_does_not_overwrite_another_editor(async_client, documents):
    old = (await async_client.get(endpoint(documents.uid))).json()
    await save(async_client, documents, HTML.replace('Note', 'New note'))
    response = await async_client.put(endpoint(documents.uid), json={'content': HTML + 'old editor',
        'revision': old['revision'], 'published_revision': old['published_revision']})
    assert response.status_code == 409
    assert b'New note' in (documents.work / PATH).read_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize('markup', ['<script>alert(1)</script>', '<p onclick="alert(1)">x</p>',
    '<a href="java&#10;script:alert(1)">x</a>', '<svg><a href="https://example.org">x</a></svg>',
    '<p style="background:url(https://example.org)">x</p>'])
async def test_unsafe_html_is_rejected_without_writes(async_client, documents, markup):
    response = await save(async_client, documents, HTML + markup)
    assert response.status_code == 422
    assert not response.json()['detail']['validation']['can_save']
    assert (documents.work / PATH).read_bytes() == HTML.encode('utf-8')


@pytest.mark.asyncio
async def test_draft_can_keep_visible_structural_errors_but_release_cannot(async_client, documents):
    content = HTML.replace('</article>', '<p id="intro">Duplicate</p><a href="#missing">Missing</a></article>')
    response = await save(async_client, documents, content)
    assert response.status_code == 200
    detail = response.json()
    assert {i['code'] for i in detail['validation']['issues']} >= {'duplicate-id', 'missing-anchor'}
    assert detail['validation']['can_save']
    publish = await async_client.post('/publication-documents/scpub1/publish/', json={'documents': [{
        'id': documents.uid, 'revision': detail['revision'], 'published_revision': detail['published_revision']} ]})
    assert publish.status_code == 422
    assert DocumentStore(documents.work, 'scpub1').read()['publish'] is None


@pytest.mark.asyncio
async def test_published_baseline_read_ignores_dirty_published_working_file(async_client, documents):
    (documents.published / PATH).write_text('not committed')
    detail = (await async_client.get(endpoint(documents.uid))).json()
    assert detail['published_content'] == HTML


@pytest.mark.asyncio
async def test_new_draft_after_publication_uses_current_published_baseline(async_client, documents):
    first_content = HTML.replace('Note', 'First release')
    first = (await save(async_client, documents, first_content)).json()
    requested = await async_client.post('/publication-documents/scpub1/publish/', json={'documents': [{
        'id': documents.uid, 'revision': first['revision'], 'published_revision': first['published_revision']}]})
    assert requested.status_code == 202

    # Model completed task bookkeeping and the merged PR arriving in published.
    store = DocumentStore(documents.work, 'scpub1')
    state = store.read()
    state['sync']['status'] = 'synced'
    state['publish']['status'] = 'synced'
    state['submitted'] = dict(state['publish']['documents'])
    store.write(state)
    (documents.published / PATH).write_bytes(first_content.encode('utf-8'))
    commit_repo(pygit2.Repository(str(documents.published)))

    merged = (await async_client.get(endpoint(documents.uid))).json()
    assert merged['content'] == merged['published_content'] == first_content
    assert merged['base_revision'] == merged['published_revision'] == revision(first_content)
    assert not merged['published_changed']
    # Reading must not rewrite state; saving must handle the persisted old baseline itself.
    assert store.read() == state
    assert state['documents'][documents.uid]['base_revision'] == revision(HTML)

    second_content = HTML.replace('Note', 'Second release')
    response = await save(async_client, documents, second_content)
    assert response.status_code == 200
    second = response.json()
    assert second['base_revision'] == revision(first_content)
    assert not second['published_changed']
    state = store.read()
    assert state['documents'][documents.uid]['base_revision'] == revision(first_content)
    assert state['sync']['documents'][documents.uid]['base_revision'] == revision(first_content)
    requested = await async_client.post('/publication-documents/scpub1/publish/', json={'documents': [{
        'id': documents.uid, 'revision': second['revision'], 'published_revision': second['published_revision']}]})
    assert requested.status_code == 202


@pytest.mark.asyncio
async def test_changed_published_baseline_requires_explicit_review(async_client, documents):
    saved = (await save(async_client, documents, HTML.replace('Note', 'Draft'))).json()
    (documents.published / PATH).write_text(HTML.replace('Note', 'Published update'))
    commit_repo(pygit2.Repository(str(documents.published)))
    stale = await async_client.put(endpoint(documents.uid), json={'content': HTML,
        'revision': saved['revision'], 'published_revision': saved['published_revision']})
    assert stale.status_code == 409
    detail = (await async_client.get(endpoint(documents.uid))).json()
    assert detail['published_changed']
    # Saving an existing divergent draft must preserve the conflict until acknowledged.
    response = await save(async_client, documents, HTML.replace('Note', 'Updated draft'))
    assert response.status_code == 200
    detail = response.json()
    assert detail['base_revision'] == revision(HTML)
    assert detail['published_changed']
    state = DocumentStore(documents.work, 'scpub1').read()
    assert state['documents'][documents.uid]['base_revision'] == revision(HTML)
    assert state['sync']['documents'][documents.uid]['base_revision'] == revision(HTML)
    blocked = await async_client.post('/publication-documents/scpub1/publish/', json={'documents': [{
        'id': documents.uid, 'revision': detail['revision'], 'published_revision': detail['published_revision']}]})
    assert blocked.status_code == 409
    acknowledged = await async_client.post(endpoint(documents.uid, '/baseline/'), json={
        'revision': detail['revision'], 'published_revision': detail['published_revision']})
    assert acknowledged.status_code == 200
    assert not acknowledged.json()['published_changed']


@pytest.mark.asyncio
async def test_shared_document_needs_all_owner_permissions(async_client, documents):
    config = documents.work / '_publication/en/alice/editions/dn/other.json'
    config.write_text(json.dumps({'publication_number': 'scpub2', 'frontmatter': ['./matter/introduction.html']}))
    assert (await async_client.get(endpoint(documents.uid))).status_code == 404
    assert (await async_client.get('/publication-documents/counts/')).json() == {'scpub1': 1}
    documents.user.role = 'administrator'
    assert (await async_client.get(endpoint(documents.uid))).status_code == 200


@pytest.mark.asyncio
async def test_symlink_and_unlisted_file_cannot_be_read_or_saved(async_client, documents, tmp_path):
    secret = tmp_path / 'secret.html'
    secret.write_text('secret')
    target = documents.work / PATH
    target.unlink(); target.symlink_to(secret)
    assert (await async_client.get(endpoint(documents.uid))).status_code == 403
    assert secret.read_text() == 'secret'
    assert (await async_client.get(endpoint(document_id(OTHER)))).status_code in (403, 404)


@pytest.mark.asyncio
async def test_release_uses_selected_saved_revisions_and_rejects_stale_selection(async_client, documents):
    detail = (await save(async_client, documents, HTML.replace('Note', 'Release'))).json()
    selection = {'id': documents.uid, 'revision': detail['revision'], 'published_revision': detail['published_revision']}
    result = await async_client.post('/publication-documents/scpub1/publish/', json={'documents': [selection]})
    assert result.status_code == 202
    state = DocumentStore(documents.work, 'scpub1').read()
    assert list(state['publish']['documents']) == [documents.uid]
    assert state['publish']['documents'][documents.uid]['revision'] == revision(detail['content'])
    assert (await async_client.post('/publication-documents/scpub1/publish/', json={'documents': [selection]})).status_code == 409


@pytest.mark.asyncio
async def test_diff_is_text_and_can_compare_unsaved_content(async_client, documents):
    response = await async_client.post(endpoint(documents.uid, '/diff/?comparison=saved'), json={'content': HTML.replace('Note', 'Difference')})
    assert response.status_code == 200
    assert '+<aside id=' in response.json()['diff']
    assert (documents.work / PATH).read_bytes() == HTML.encode('utf-8')
