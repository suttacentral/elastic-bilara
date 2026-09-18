"""Audit prepared structure operations; --apply resumes verified records.

Run inside the configured backend environment. A complete backup is made before
recovery. Files differing from both journal snapshots are never overwritten.
"""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from copy import deepcopy

from app.core.config import settings
from app.services.projects.structure_service import _complete, publish_structure_result
from app.services.projects.structure_store import StructureStore
from search.search import Search


def restore_completed(work, operation_id, archive, apply):
    paths = list(work.parent.glob(f'.structure-operations/*/{UUID(operation_id)}.json'))
    if len(paths) != 1:
        raise RuntimeError(f'Expected one completed operation: {operation_id}')
    original = json.loads(paths[0].read_text())
    store = StructureStore(work, work / original['preview']['root'])
    with store.lock():
        store.check_ready()
        changed = [p for p, after in original['files'].items()
                   if json.loads((work / p).read_text()) != after]
        if changed:
            raise RuntimeError(f'Later edits detected; refusing to restore: {changed}')
        summary = {'restore': operation_id, 'root': original['preview']['root'], 'files': len(original['files'])}
        if apply:
            destination = archive / operation_id
            destination.mkdir(parents=True)
            shutil.copy2(paths[0], destination / 'completed.json')
            for relative in original['files']:
                target = destination / 'files' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(work / relative, target)
            preview = deepcopy(original['preview'])
            files = {}
            for project in preview['projects']:
                relative = project['path']
                files[relative] = project['before']
                project['data'] = project['before']
                project['before'] = original['files'][relative]
                project['muid'] = '-'.join(Path(relative).parts[:3])
            preview.update(operation='restore', splitter_uid=None, merger_uid=None, mergee_uid=None, manual_projects=[])
            record = {'operation_id': str(uuid4()), 'fingerprint': 'restore:' + operation_id,
                      'operation': 'restored', 'preview': preview, 'user': original['user'], 'files': files}
            store.prepare(record)
            result = _complete(store, record, Search())
            summary.update(status=result['status'], backup=str(destination))
            assert all(json.loads((work / p).read_text()) == data for p, data in files.items())
    if apply:
        result = publish_structure_result(store.root, record, result)
        summary['publication_status'] = result['publication_status']
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--restore-completed', action='append', default=[])
    args = parser.parse_args()
    work = settings.WORK_DIR.resolve()
    archive = work.parent / ('.structure-recovery-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if args.restore_completed:
        for operation_id in args.restore_completed:
            restore_completed(work, operation_id, archive, args.apply)
        return
    for journal in sorted(work.parent.glob('.structure-operations/*/pending.json')):
        record = json.loads(journal.read_text())
        if not record:
            continue
        store = StructureStore(work, work / record['preview']['root'])
        with store.lock():
            record = store.pending()
            if not record:
                continue
            before = {p['path']: p['before'] for p in record['preview']['projects']}
            changed = []
            counts = {'after': 0, 'before': 0}
            for relative, after in record['files'].items():
                path = (work / relative).resolve()
                path.relative_to(work)
                actual = json.loads(path.read_text())
                if actual == after:
                    counts['after'] += 1
                elif actual == before[relative]:
                    counts['before'] += 1
                else:
                    changed.append(relative)
            summary = {'operation_id': record['operation_id'], 'root': record['preview']['root'],
                       'files': counts, 'unexpected_changes': changed}
            if changed:
                print(json.dumps(summary), flush=True)
                raise RuntimeError('Files have changed outside this operation; recovery stopped')
            if args.apply:
                destination = archive / record['operation_id']
                destination.mkdir(parents=True)
                shutil.copy2(journal, destination / 'pending.json')
                for relative in record['files']:
                    target = destination / 'files' / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(work / relative, target)
                result = _complete(store, record, Search())
                summary['status'] = result['status']
                summary['backup'] = str(destination)
                store.check_ready()
                assert all(json.loads((work / p).read_text()) == data for p, data in record['files'].items())
        if args.apply:
            result = publish_structure_result(store.root, record, result)
            summary['publication_status'] = result['publication_status']
        print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
