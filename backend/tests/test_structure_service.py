"""Integration tests with real files, validators and journals; no Git/ES writes."""
import json
import fcntl
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from search.search import Search

# These tests use a mock search service; importing the application must not
# create or populate real Elasticsearch indexes.
with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app.services.projects import structure_service as service
from app.services.projects.models import StructureCommitIn
from app.services.projects.utils import SplitMergePublishResult
from app.services.projects.structure_store import StructureStore, StructureConflict
from app.services.projects.virtual_projects import VirtualProjectFile


class StructureServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name) / 'unpublished'
        self.root = self.work / 'root/pli/ms/sutta/dn1_root-pli-ms.json'
        self.html = self.work / 'html/pli/ms/sutta/dn1_html.json'
        self.comment = self.work / 'comment/en/u/sutta/dn1_comment-en-u.json'
        for path, data in [(self.root, {'dn1:1.1': 'A ', 'dn1:1.2': 'B ', 'dn1:1.3': 'C '}),
                           (self.html, {'dn1:1.1': '<p>{}', 'dn1:1.2': '{}', 'dn1:1.3': '{}</p>'}),
                           (self.comment, {'dn1:1.1': 'a ', 'dn1:1.2': 'b ', 'dn1:1.3': 'c '})]:
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data))
        patcher = patch.object(service.settings, 'WORK_DIR', self.work)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.search = Mock()
        self.search.get_file_paths.side_effect = lambda **kwargs: {str(self.root)}
        self.search.replace_structure_segments.return_value = (True, None)
        self.user = SimpleNamespace(github_id=1, username='admin')
        patcher = patch.object(service, 'schedule_split_merge_auto_publish', return_value=SplitMergePublishResult(
            auto_published_paths=['/root/test'], manual_publish_paths=[], task_id='task'))
        self.publish = patcher.start()
        self.addCleanup(patcher.stop)

    def payload(self, operation='merge', uid='dn1:1.1'):
        preview = service.preview(self.root, operation, uid)
        edits = {'html-pli-ms': {'dn1:1.1': '<p>{}'}}
        if operation == 'split':
            edits['html-pli-ms']['dn1:1.2'] = '{}'
            edits['root-pli-ms'] = {'dn1:1.1': 'first ', 'dn1:1.2': 'second '}
        return StructureCommitIn(muid='root-pli-ms', prefix='dn1', operation=operation,
                                 uid=uid, operation_id=uuid4(), revision=preview['revision'],
                                 edits=edits, reviewed=preview['manual_projects'])

    def test_read_project_returns_data_and_revision_under_shared_lock(self):
        virtual = VirtualProjectFile(self.root, 'root-pli-ms',
                                     self.work / 'translation/en/u/dn1_translation-en-u.json',
                                     'translation-en-u', 'dn1')
        store = StructureStore(self.work, self.root)
        expected_revision = store.revision()
        read_data = service.get_json_data
        revision = StructureStore.revision

        def assert_shared_lock():
            with (store.directory / 'lock').open('a+') as handle:
                fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def locked_read(path):
            assert_shared_lock()
            return read_data(path)

        def locked_revision(current_store, root_data=None):
            assert_shared_lock()
            return revision(current_store, root_data)

        for project in [self.root, self.comment, virtual]:
            with self.subTest(project=project), patch.object(service, 'get_json_data', locked_read), patch.object(
                StructureStore, 'revision', locked_revision
            ):
                result = service.read_project(project)
            self.assertEqual(result, {
                'data': {} if project == virtual else read_data(project),
                'materialized': project != virtual,
                'structure_revision': expected_revision,
            })
        self.assertFalse(virtual.target_path.exists())

    def test_read_project_rejects_pending_before_reading_data(self):
        virtual = VirtualProjectFile(self.root, 'root-pli-ms',
                                     self.work / 'translation/en/u/dn1_translation-en-u.json',
                                     'translation-en-u', 'dn1')
        store = StructureStore(self.work, self.root)
        with store.lock():
            store.prepare({'operation_id': str(uuid4())})
        with patch.object(service, 'get_json_data') as read_data:
            for project in [self.root, self.comment, virtual]:
                with self.subTest(project=project), self.assertRaises(StructureConflict):
                    service.read_project(project)
            read_data.assert_not_called()

    def test_split_and_merge_queue_every_affected_type(self):
        for kind in ['translation', 'reference', 'variant', 'tag']:
            path = self.work / kind / f'en/u/dn1_{kind}-en-u.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'dn1:1.1': '', 'dn1:1.2': '', 'dn1:1.3': ''}))
        (self.work / '_tags.json').write_text('[]')
        for operation in ['split', 'merge']:
            with self.subTest(operation=operation):
                result = service.commit_operation(self.root, self.payload(operation), self.search, self.user)
                paths = self.publish.call_args.args[1]
                self.assertEqual({p.relative_to(self.work).parts[0] for p in paths},
                                 {'root', 'html', 'comment', 'translation', 'reference', 'variant', 'tag'})
                self.assertEqual(len(paths), 7)
                self.assertEqual(result['manual_publish_paths'], [])

    def test_merge_persists_manual_edits_and_retry_does_not_merge_twice(self):
        payload = self.payload()
        result = service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(json.loads(self.root.read_text())['dn1:1.1'], 'A B ')
        self.assertEqual(json.loads(self.comment.read_text()), {'dn1:1.1': 'a | b ', 'dn1:1.2': 'c '})
        self.assertEqual(json.loads(self.html.read_text()), {'dn1:1.1': '<p>{}', 'dn1:1.2': '{}</p>'})
        self.assertEqual(service.commit_operation(self.root, payload, self.search, self.user), result)
        self.publish.assert_called_once()
        self.assertEqual(self.search.replace_structure_segments.call_count, 3)

    def test_completion_writes_head_once_and_returns_persisted_revision(self):
        payload = self.payload()
        writes = []
        write_json = StructureStore.write_json

        def track_write(store, path, value):
            writes.append(Path(path).name)
            return write_json(store, path, value)

        with patch.object(StructureStore, 'write_json', track_write):
            result = service.commit_operation(self.root, payload, self.search, self.user)
        store = StructureStore(self.work, self.root)
        self.assertEqual(writes.count('head.json'), 1)
        self.assertEqual(result['structure_revision'], store.revision())
        self.assertEqual(store.get(payload.operation_id)['result']['structure_revision'], store.revision())

    def test_value_error_after_prepare_keeps_operation_recoverable(self):
        payload = self.payload()
        failure = ValueError('write interrupted')
        with patch.object(StructureStore, 'apply', side_effect=failure):
            with self.assertRaisesRegex(service.StructureOperationIncomplete, 'pending') as caught:
                service.commit_operation(self.root, payload, self.search, self.user)
        self.assertIs(caught.exception.__cause__, failure)
        store = StructureStore(self.work, self.root)
        self.assertEqual(store.pending()['operation_id'], str(payload.operation_id))
        result = service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(json.loads(self.root.read_text())['dn1:1.1'], 'A B ')
        self.assertIsNone(store.pending())

    def test_submission_rejection_exposes_business_reason(self):
        for failure, reason in [(ValueError('invalid input'), 'invalid_input'),
                                (StructureConflict('stale preview'), 'conflict')]:
            payload = self.payload()
            with self.subTest(reason=reason), patch.object(service, 'preview_locked', side_effect=failure):
                with self.assertRaises(service.SubmissionRejected) as caught:
                    service.commit_operation(self.root, payload, self.search, self.user)
                self.assertEqual(caught.exception.reason, reason)
                self.assertEqual(str(caught.exception), str(failure))
                self.assertIs(caught.exception.__cause__, failure)
                self.assertIsNone(StructureStore(self.work, self.root).pending())

    def test_split_persists_both_edited_root_segments(self):
        result = service.commit_operation(self.root, self.payload('split'), self.search, self.user)
        data = json.loads(self.root.read_text())
        self.assertEqual(data['dn1:1.1'], 'first ')
        self.assertEqual(data['dn1:1.2'], 'second ')
        self.assertEqual(data['dn1:1.3'], 'B ')
        self.assertEqual(result['status'], 'complete')

    def test_stale_preview_and_invalid_html_do_not_write(self):
        payload = self.payload()
        original = self.root.read_text()
        self.comment.write_text(self.comment.read_text().replace('a ', 'changed '))
        with self.assertRaises(StructureConflict):
            service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(self.root.read_text(), original)
        payload = self.payload()
        payload.edits['html-pli-ms']['dn1:1.1'] = '{}{}'
        with self.assertRaises(ValueError):
            service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(self.root.read_text(), original)
        self.publish.assert_not_called()

    def test_index_failure_is_pending_and_status_resumes(self):
        payload = self.payload()
        self.search.replace_structure_segments.return_value = (False, RuntimeError('offline'))
        with self.assertRaises(RuntimeError):
            service.commit_operation(self.root, payload, self.search, self.user)
        self.publish.assert_not_called()
        with self.assertRaises(StructureConflict):
            service.preview(self.root, 'split', 'dn1:1.1')
        self.search.replace_structure_segments.return_value = (True, None)
        result = service.operation_status(self.root, payload.operation_id, self.search, self.user)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(json.loads(self.root.read_text())['dn1:1.1'], 'A B ')

    def test_publication_runs_after_commit_without_holding_text_lock(self):
        def enqueue(*args):
            store = StructureStore(self.work, self.root)
            store.check_ready()
            with (store.directory / 'lock').open('a+') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return SplitMergePublishResult(task_id='task', auto_published_paths=[], manual_publish_paths=[])
        self.publish.side_effect = enqueue
        result = service.commit_operation(self.root, self.payload(), self.search, self.user)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['publication_status'], 'scheduled')

    def test_publication_failure_does_not_replay_or_requeue_on_duplicate_commit(self):
        payload = self.payload()
        self.publish.side_effect = RuntimeError('broker offline')
        result = service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['publication_status'], 'failed')
        self.assertEqual(result['auto_published_paths'], [])
        self.assertIn('/' + self.root.relative_to(self.work).as_posix(), result['auto_publish_pending_paths'])
        store = StructureStore(self.work, self.root)
        store.check_ready()
        self.assertEqual(store.get(str(payload.operation_id))['result']['publication_status'], 'failed')
        service.preview(self.root, 'split', 'dn1:1.1')
        later = {'dn1:1.1': 'later edit', 'dn1:1.2': 'C '}
        self.root.write_text(json.dumps(later))
        revision = store.revision()
        self.search.reset_mock()
        self.publish.side_effect = None
        result = service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(result['publication_status'], 'failed')
        self.assertEqual(json.loads(self.root.read_text()), later)
        self.assertEqual(store.revision(), revision)
        self.search.replace_structure_segments.assert_not_called()
        self.assertEqual(service.commit_operation(self.root, payload, self.search, self.user), result)
        self.publish.assert_called_once()

    def test_status_reports_publication_failure_without_replaying_structure(self):
        payload = self.payload()
        self.publish.side_effect = ValueError('author unavailable')
        service.commit_operation(self.root, payload, self.search, self.user)
        self.search.reset_mock()
        result = service.operation_status(self.root, payload.operation_id, self.search, self.user)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['publication_status'], 'failed')
        self.search.replace_structure_segments.assert_not_called()

    def test_duplicate_commit_during_enqueue_does_not_queue_again(self):
        payload = self.payload()
        queued = self.publish.return_value

        def enqueue(*args):
            duplicate = service.commit_operation(self.root, payload, self.search, self.user)
            self.assertEqual(duplicate['status'], 'complete')
            self.assertEqual(duplicate['publication_status'], 'pending')
            return queued

        self.publish.side_effect = enqueue
        result = service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(result['publication_status'], 'scheduled')
        self.publish.assert_called_once()
        self.assertEqual(self.search.replace_structure_segments.call_count, 3)

    def test_interruption_after_structure_completion_requires_manual_publication(self):
        payload = self.payload()
        service._commit_structure(self.root, payload, self.search, self.user)
        self.publish.assert_not_called()
        self.search.reset_mock()
        status = service.operation_status(self.root, payload.operation_id, self.search, self.user)
        self.assertEqual(status['status'], 'complete')
        self.assertEqual(status['publication_status'], 'pending')
        service.preview(self.root, 'split', 'dn1:1.1')
        result = service.commit_operation(self.root, payload, self.search, self.user)
        self.assertEqual(result['publication_status'], 'pending')
        self.search.replace_structure_segments.assert_not_called()
        self.publish.assert_not_called()

    def test_resuming_structure_queues_with_original_author(self):
        payload = self.payload()
        self.search.replace_structure_segments.return_value = (False, RuntimeError('offline'))
        with self.assertRaises(RuntimeError):
            service.commit_operation(self.root, payload, self.search, self.user)
        self.search.replace_structure_segments.return_value = (True, None)
        operator = SimpleNamespace(github_id=2, username='operator')
        with patch.object(service, 'get_user', return_value=self.user) as get_user:
            service.operation_status(self.root, payload.operation_id, self.search, operator)
        get_user.assert_called_once_with(1)
        self.assertEqual(self.publish.call_args.args[0], self.user)

    def test_unknown_directory_is_discovered_and_blocked(self):
        path = self.work / 'foo/en/u/dn1_foo-en-u.json'
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'merge.json'):
            service.preview(self.root, 'merge', 'dn1:1.1')

    def test_nonroot_target_is_rejected(self):
        with self.assertRaises(ValueError):
            service.resolve_root('translation-en-u', 'dn1', self.search)

    def test_split_without_html_edit_is_rejected_before_any_write(self):
        payload = self.payload('split')
        payload.edits = {}
        original = {path: path.read_bytes() for path in [self.root, self.html, self.comment]}
        with self.assertRaisesRegex(ValueError, 'html-pli-ms: dn1:1.2'):
            service.commit_operation(self.root, payload, self.search, self.user)
        self.assertTrue(all(path.read_bytes() == data for path, data in original.items()))
        self.assertIsNone(StructureStore(self.work, self.root).pending())
        self.publish.assert_not_called()


class StructureApiTests(unittest.IsolatedAsyncioTestCase):
    setUp = StructureServiceTests.setUp
    payload = StructureServiceTests.payload

    async def asyncSetUp(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from app.api.api_v1.endpoints import projects
        self.projects = projects
        app = FastAPI()
        app.include_router(projects.router)
        app.dependency_overrides[projects.utils.get_current_user] = lambda: self.user
        self.client = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)
        patcher = patch.object(projects, 'search', self.search)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user.is_active = True
        self.user.role = 'administrator'
        patcher = patch('app.services.users.permissions.get_user_from_cookie', return_value=self.user)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_root_get_allows_concurrent_readers_without_rereading_root(self):
        store = StructureStore(self.work, self.root)
        expected_revision = store.revision()
        store.directory.mkdir(parents=True)
        flock = fcntl.flock
        with (store.directory / 'lock').open('a+') as reader:
            flock(reader, fcntl.LOCK_SH)
            with patch.object(self.projects, 'can_edit_translation', return_value=True), patch(
                'fcntl.flock', side_effect=lambda fd, mode: flock(fd, mode | fcntl.LOCK_NB)
            ), patch.object(Path, 'read_text', side_effect=AssertionError('Root read twice')):
                response = self.projects.get_json_data_for_prefix_in_project(self.user, 'root-pli-ms', 'dn1')
        self.assertEqual(response.structure_revision, expected_revision)
        self.assertEqual(response.data, json.loads(self.root.read_text()))

    async def test_get_project_preserves_snapshot_response_and_pending_conflict(self):
        virtual = VirtualProjectFile(self.root, 'root-pli-ms',
                                     self.work / 'translation/en/u/dn1_translation-en-u.json',
                                     'translation-en-u', 'dn1')
        store = StructureStore(self.work, self.root)
        expected_revision = store.revision()
        for pending in [False, True]:
            if pending:
                with store.lock():
                    store.prepare({'operation_id': str(uuid4())})
            for muid, path in [('root-pli-ms', self.root), ('comment-en-u', self.comment),
                               ('translation-en-u', None)]:
                with self.subTest(pending=pending, muid=muid), patch.object(
                    self.projects, '_get_project_file_paths', return_value={str(path)} if path else set()
                ), patch.object(self.projects, 'resolve_virtual_file', return_value=virtual), patch.object(
                    self.projects, 'can_edit_translation', return_value=True
                ):
                    response = await self.client.get(f'/projects/{muid}/dn1/')
                self.assertEqual(response.status_code, 409 if pending else 200, response.text)
                if pending:
                    self.assertIn('pending', response.json()['detail'])
                else:
                    self.assertEqual(response.json(), {
                        'can_edit': True, 'data': json.loads(path.read_text()) if path else {},
                        'task_id': None, 'materialized': path is not None,
                        'structure_revision': expected_revision,
                    })
        self.assertFalse(virtual.target_path.exists())

    async def test_admin_and_superuser_allowed_writer_and_inactive_denied(self):
        body = {'muid': 'root-pli-ms', 'prefix': 'dn1', 'operation': 'merge', 'uid': 'dn1:1.1'}
        for role in ['administrator', 'superuser']:
            self.user.role = role
            response = await self.client.post('/projects/structure/preview/', json=body)
            self.assertEqual(response.status_code, 200, response.text)
        self.user.role = 'writer'
        response = await self.client.post('/projects/structure/preview/', json=body)
        self.assertIn(response.status_code, [401, 403])
        self.user.role = 'administrator'
        self.user.is_active = False
        response = await self.client.post('/projects/structure/preview/', json=body)
        self.assertEqual(response.status_code, 401)

    async def test_old_save_version_rejected_after_structure_commit(self):
        revision = StructureStore(self.work, self.root).revision()
        response = await self.client.patch('/projects/merge/', json=self.payload().model_dump(mode='json'))
        self.assertEqual(response.status_code, 200, response.text)
        with patch.object(self.projects, 'can_edit_translation', return_value=True), patch.object(
            self.projects, 'resolve_virtual_file', return_value=None
        ), patch('app.services.projects.utils.get_user', return_value=self.user):
            response = await self.client.patch('/projects/root-pli-ms/dn1/',
                headers={'X-Structure-Revision': revision}, json={'dn1:1.2': 'stale edit'})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(json.loads(self.root.read_text())['dn1:1.2'], 'C ')

    async def test_confirm_requires_root_and_preview_protocol(self):
        payload = self.payload().model_dump(mode='json')
        payload['muid'] = 'comment-en-u'
        response = await self.client.patch('/projects/merge/', json=payload)
        self.assertEqual(response.status_code, 400)
        response = await self.client.patch('/projects/merge/', json={'muid': 'root-pli-ms', 'prefix': 'dn1', 'merger_uid': 'dn1:1.1', 'mergee_uid': 'dn1:1.2'})
        self.assertEqual(response.status_code, 422)

    async def test_stale_preview_is_an_explicit_submission_rejection(self):
        payload = self.payload()
        self.comment.write_text(self.comment.read_text().replace('a ', 'changed '))
        response = await self.client.patch('/projects/merge/', json=payload.model_dump(mode='json'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail']['code'], 'submission_rejected')
        self.assertIsNone(StructureStore(self.work, self.root).pending())

    async def test_structure_endpoints_preserve_plain_error_responses(self):
        payload = self.payload()
        requests = [
            ('POST', '/projects/structure/preview/',
             {'muid': payload.muid, 'prefix': payload.prefix, 'operation': payload.operation, 'uid': payload.uid}),
            ('POST', '/projects/structure/status/',
             {'muid': payload.muid, 'prefix': payload.prefix, 'operation_id': str(payload.operation_id)}),
            ('PATCH', '/projects/merge/', payload.model_dump(mode='json')),
        ]
        for failure, code in [(ValueError('invalid target'), 400), (StructureConflict('pending'), 409)]:
            for method, url, body in requests:
                with self.subTest(url=url, code=code), patch.object(service, 'resolve_root', side_effect=failure):
                    response = await self.client.request(method, url, json=body)
                self.assertEqual(response.status_code, code)
                self.assertEqual(response.json(), {'detail': str(failure)})

    async def test_prepared_failure_returns_500_and_status_recovers(self):
        await self.assert_failure_response_and_recovery(
            patch.object(StructureStore, 'apply', side_effect=ValueError('write interrupted')))

    async def test_index_failure_returns_500_and_status_recovers(self):
        await self.assert_failure_response_and_recovery(
            patch.object(self.search, 'replace_structure_segments', return_value=(False, RuntimeError('offline'))))

    async def test_io_failure_returns_500_and_status_recovers(self):
        await self.assert_failure_response_and_recovery(
            patch.object(StructureStore, 'apply', side_effect=OSError('disk unavailable')))

    async def assert_failure_response_and_recovery(self, failure):
        payload = self.payload()
        status_payload = dict(muid=payload.muid, prefix=payload.prefix, operation_id=str(payload.operation_id))
        with failure:
            response = await self.client.patch('/projects/merge/', json=payload.model_dump(mode='json'))
            retry_response = await self.client.post('/projects/structure/status/', json=status_payload)
        for result in [response, retry_response]:
            self.assertEqual(result.status_code, 500)
            self.assertEqual(result.json()['detail'], {
                'code': 'structure_operation_incomplete',
                'message': 'Structure operation is incomplete. Retry confirmation or reload to resume it.',
                'operation_id': str(payload.operation_id),
            })
        store = StructureStore(self.work, self.root)
        self.assertEqual(store.pending()['operation_id'], str(payload.operation_id))
        response = await self.client.post('/projects/structure/status/', json={
            'muid': payload.muid, 'prefix': payload.prefix, 'operation_id': str(payload.operation_id),
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'complete')
        self.assertIsNone(store.pending())

    async def test_invalid_html_is_an_explicit_submission_rejection(self):
        payload = self.payload()
        payload.edits['html-pli-ms']['dn1:1.1'] = '{}{}'
        response = await self.client.patch('/projects/merge/', json=payload.model_dump(mode='json'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail']['code'], 'submission_rejected')

    async def test_reused_id_with_different_content_is_not_discardable(self):
        payload = self.payload()
        service.commit_operation(self.root, payload, self.search, self.user)
        payload.edits = {}
        response = await self.client.patch('/projects/merge/', json=payload.model_dump(mode='json'))
        self.assertEqual(response.status_code, 409)
        self.assertIsInstance(response.json()['detail'], str)

    async def test_enqueue_failure_returns_saved_result_without_requeueing(self):
        payload = self.payload().model_dump(mode='json')
        self.publish.side_effect = RuntimeError('broker offline')
        response = await self.client.patch('/projects/merge/', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'complete')
        self.assertEqual(response.json()['publication_status'], 'failed')
        repeated = await self.client.patch('/projects/merge/', json=payload)
        self.assertEqual(repeated.json(), response.json())
        self.publish.assert_called_once()
        self.assertEqual(self.search.replace_structure_segments.call_count, 3)


if __name__ == '__main__':
    unittest.main()
