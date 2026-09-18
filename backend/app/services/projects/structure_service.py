"""Application boundary for previewing and committing structural changes."""
import json
import logging
from pathlib import Path
from typing import Literal

from app.core.config import settings
from app.services.projects.structure_engine import build_preview, apply_edits, load_rules, digest
from app.services.projects.structure_store import StructureStore, StructureConflict
from app.services.projects.html_validator import validate_bilara_html
from app.services.projects.utils import (
    schedule_split_merge_auto_publish,
    format_split_merge_publish_path,
)
from app.services.users.utils import get_user
from app.services.projects.virtual_projects import VirtualProjectFile
from search.utils import find_root_path, get_json_data

logger = logging.getLogger(__name__)


def read_project(project: Path | VirtualProjectFile) -> dict:
    """Read project data and its structure revision in one shared-lock snapshot."""
    virtual = isinstance(project, VirtualProjectFile)
    root = project.source_path if virtual else find_root_path(project)
    store = StructureStore(settings.WORK_DIR, root)
    with store.lock(shared=True):
        store.check_ready()
        data = {} if virtual else get_json_data(project)
        revision = store.revision(data if not virtual and project == root else None)
    return {'data': data, 'materialized': not virtual, 'structure_revision': revision}


class SubmissionRejected(StructureConflict):
    """Preflight rejection after checking that this operation has no journal."""

    def __init__(self, message: str, reason: Literal['invalid_input', 'conflict']):
        super().__init__(message)
        self.reason = reason


class StructureOperationIncomplete(RuntimeError):
    """A prepared operation failed to complete and must remain recoverable."""

    def __init__(self, operation_id):
        self.operation_id = str(operation_id)
        super().__init__(f'Operation {self.operation_id} is pending')


def resolve_root(muid, prefix, search):
    if not muid.startswith('root-'):
        raise ValueError('Split/merge must operate on a root project')
    paths = list(search.get_file_paths(muid=muid, prefix=prefix, exact=True, _type='file_path'))
    if len(paths) != 1:
        raise ValueError('Expected exactly one root file')
    root = Path(paths[0]).resolve()
    if root.relative_to(settings.WORK_DIR.resolve()).parts[0] != 'root':
        raise ValueError('Split/merge must operate on a root file')
    return root


def preview_locked(root, operation, uid):
    work = settings.WORK_DIR.resolve()
    prefix = root.stem.split('_', 1)[0]
    files = {}
    rules = load_rules(operation)
    paths = sorted(work.glob(f'*/**/{prefix}_*.json'))
    roots = [path for path in paths if path.relative_to(work).parts[0] == 'root']
    if roots != [root]:
        raise ValueError('The text prefix must identify exactly one root file')
    # Discover actual types, including ones absent from the configuration/enum.
    for path in paths:
        if path.resolve() != path:
            raise ValueError(f'Symlinked project is not supported: {path.name}')
        relative = path.relative_to(work).as_posix()
        if relative.split('/')[0] not in rules:
            raise ValueError(f'Data type `{relative.split("/")[0]}` is not found in `{operation}.json`. Please add it before proceeding.')
        files[relative] = json.loads(path.read_text(encoding='utf-8'))
    root_key = root.relative_to(work).as_posix()
    if root_key not in files:
        raise ValueError('Root file was not found in related projects')
    return build_preview(files, root_key, operation, uid, rules)


def preview(root, operation, uid):
    store = StructureStore(settings.WORK_DIR, root)
    with store.lock():
        store.check_ready()
        result = preview_locked(root, operation, uid)
        result['structure_revision'] = store.revision()
        result['revision'] = digest([result['revision'], result['structure_revision']])
        return result


def _complete(store, record, search):
    try:
        return _finish_operation(store, record, search)
    except Exception as error:
        # A prepared operation must not be mistaken for a preflight rejection:
        # its journal must remain available for recovery.
        logger.exception('Structure operation %s could not complete', record['operation_id'])
        raise StructureOperationIncomplete(record['operation_id']) from error


def _finish_operation(store, record, search):
    completed = store.get(record['operation_id'])
    if completed:
        # A crash after recording the result but before clearing pending is safe.
        store.write_json(store.directory / 'pending.json', None)
        return completed['result']
    store.apply(record)
    previous = {project['path']: list(project['before']) for project in record['preview']['projects']}
    for relative in record['files']:
        indexed, error = search.replace_structure_segments(store.work / relative, previous[relative])
        if not indexed:
            raise RuntimeError(f'Could not index {relative}: {error}')
    # Finish the structure before contacting the publication queue.
    publication = {'auto_published_paths': [],
                   'auto_publish_pending_paths': [format_split_merge_publish_path(store.work / p) for p in record['files']],
                   'manual_publish_paths': [], 'auto_publish_task_id': None,
                   'publication_status': 'pending'}
    result = {**record['preview'], **publication, 'operation_id': record['operation_id'],
              'message': 'Structure operation completed', 'status': 'complete'}
    for project in result['projects']:
        project['data'] = record['files'][project['path']]
    store.finish(record, result)
    return result


def commit_operation(root, payload, search, user):
    result, record = _commit_structure(root, payload, search, user)
    return publish_structure_result(root, record, result, user) if record else result


def _commit_structure(root, payload, search, user):
    store = StructureStore(settings.WORK_DIR, root)
    fingerprint = digest(payload.model_dump(mode='json'))
    operation_id = str(payload.operation_id)
    with store.lock():
        completed = store.get(operation_id)
        if completed:
            if completed['fingerprint'] != fingerprint:
                raise StructureConflict('Operation ID was already used for another request')
            pending = store.pending()
            if pending and pending['operation_id'] == operation_id:
                store.write_json(store.directory / 'pending.json', None)
            return completed['result'], None
        pending = store.pending()
        if pending:
            if pending['operation_id'] != operation_id or pending['fingerprint'] != fingerprint:
                raise StructureConflict('Another structure operation is pending. Resume it first.')
            return _complete(store, pending, search), pending
        try:
            planned = preview_locked(root, payload.operation, payload.uid)
            planned['revision'] = digest([planned['revision'], store.revision()])
            if planned['revision'] != payload.revision:
                raise StructureConflict('Project data or rules changed. Cancel and generate a new preview; your draft has been kept.')
            edited = apply_edits(planned, payload.edits, payload.reviewed)
            names = None
            for muid, data in edited.items():
                if muid.startswith('html-'):
                    validation = validate_bilara_html(data)
                    if not validation.valid:
                        issue = validation.errors[0]
                        raise ValueError(f'{muid}: {issue.uid}: {issue.message}')
                if muid.startswith('tag-'):
                    if names is None:
                        definitions = json.loads((settings.WORK_DIR / '_tags.json').read_text())
                        names = {entry['tag'] for entry in definitions}
                    for value in data.values():
                        if {item.strip() for item in value.split(',') if item.strip()} - names:
                            raise ValueError(f'Unknown tag in {muid}')
        except ValueError as error:
            raise SubmissionRejected(str(error), 'conflict' if isinstance(error, StructureConflict) else 'invalid_input') from error
        record = {'operation_id': operation_id, 'fingerprint': fingerprint,
                  'operation': payload.operation, 'preview': planned,
                  'user': str(user.github_id),
                  'files': {p['path']: edited[p['muid']] for p in planned['projects']}}
        store.prepare(record)
        return _complete(store, record, search), record


def operation_status(root, operation_id, search, user):
    store = StructureStore(settings.WORK_DIR, root)
    with store.lock():
        completed = store.get(str(operation_id))
        pending = store.pending()
        if completed:
            if pending and pending['operation_id'] == str(operation_id):
                store.write_json(store.directory / 'pending.json', None)
            return completed['result']
        if pending and pending['operation_id'] == str(operation_id):
            result = _complete(store, pending, search)
        else:
            return {'status': 'not_found'}
    return publish_structure_result(root, pending, result, user)


def publish_structure_result(root, record, result, user=None):
    """Attempt enqueueing once after completing a structure; persist the outcome."""
    store = StructureStore(settings.WORK_DIR, root)
    try:
        author = user if user is not None and str(user.github_id) == record['user'] else get_user(int(record['user']))
        published = schedule_split_merge_auto_publish(
            author, [store.work / p for p in record['files']], record['operation'])
    except Exception:
        logger.exception('Could not queue publication for structure operation %s; files: %s',
                         record['operation_id'], list(record['files']))
        result = {**result, 'publication_status': 'failed',
                  'publication_error': 'Structure changes are saved. Automatic publication could not be queued. Commit and push the affected files using the Git commit action.'}
    else:
        result = {**result, 'publication_status': 'scheduled', 'publication_error': None,
                  'auto_publish_pending_paths': [],
                  'auto_published_paths': published.auto_published_paths,
                  'auto_publish_task_id': published.task_id}
    store.write_json(store.directory / f"{record['operation_id']}.json", {**record, 'result': result})
    return result
