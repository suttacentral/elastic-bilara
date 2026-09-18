"""Read-only verification of restored files, both ES indexes and project GETs."""
import asyncio
import json
from pathlib import Path

from elasticsearch import helpers
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.api_v1.endpoints import projects
from app.core.config import settings
from app.services.projects.structure_store import StructureStore
from app.services.users.utils import get_user
from search.search import Search
from search.utils import create_doc_id


async def main():
    work = settings.WORK_DIR.resolve()
    search = Search()
    count = 0
    for file in sorted(work.parent.glob('.structure-operations/*/*.json')):
        record = json.loads(file.read_text())
        if not isinstance(record, dict) or record.get('operation') != 'restored':
            continue
        root = work / record['preview']['root']
        store = StructureStore(work, root)
        with store.lock():
            store.check_ready()
            for relative, expected in record['files'].items():
                path = work / relative
                assert json.loads(path.read_text()) == expected, relative
                doc_id = create_doc_id(path)
                indexed = search._search.get(index=settings.ES_INDEX, id=doc_id)['_source']
                assert {s['uid']: s['segment'] for s in indexed['segments']} == expected, relative
                hits = helpers.scan(search._search, index=settings.ES_SEGMENTS_INDEX,
                                    query={'query': {'term': {'main_doc_id': doc_id}}})
                assert {h['_source']['uid']: h['_source']['segment'] for h in hits} == expected, relative
                count += 1
        app = FastAPI()
        app.include_router(projects.router)
        user = get_user(int(record['user']))
        app.dependency_overrides[projects.utils.get_current_user] = lambda: user
        async with AsyncClient(app=app, base_url='http://verification') as client:
            prefix = root.stem.split('_', 1)[0]
            for project in record['preview']['projects']:
                if not project['muid'].startswith(('root-', 'html-')):
                    continue
                response = await client.get(f"/projects/{project['muid']}/{prefix}/")
                assert response.status_code == 200, response.text
                assert response.json()['data'] == record['files'][project['path']]
                assert response.json()['structure_revision'] == store.revision()
        print(json.dumps({'root': record['preview']['root'], 'files_and_indexes': 'verified', 'project_get': 200}), flush=True)
    print(f'Verified {count} restored files and their search records', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
