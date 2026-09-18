"""Opt-in real Elasticsearch regression; uses and removes only unique test indices."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.core.config import settings
from search.search import Search
from search.utils import create_doc_id


@unittest.skipUnless(os.environ.get('BILARA_TEST_REAL_ES') == '1', 'requires dedicated temporary ES indices')
class StructureSearchTests(unittest.TestCase):
    def test_replacement_works_with_unrefreshed_updates_and_is_idempotent(self):
        search = Search()
        client = search._search
        indices = [f'bilara-structure-test-{uuid4().hex}' for _ in range(2)]
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'unpublished'
            path = work / 'root/pli/ms/sn1_root-pli-ms.json'
            path.parent.mkdir(parents=True)
            before = {'sn1:1.1': 'a ', 'sn1:1.2': 'b ', 'sn1:1.3': 'c '}
            path.write_text(json.dumps(before))
            try:
                for index in indices:
                    client.indices.create(index=index, settings={'refresh_interval': '-1', 'number_of_replicas': 0})
                with patch.object(settings, 'WORK_DIR', work), patch.object(settings, 'ES_INDEX', indices[0]), patch.object(settings, 'ES_SEGMENTS_INDEX', indices[1]):
                    search.add_to_index(path)
                    client.indices.refresh(index=indices[1])
                    # Update existing IDs but deliberately leave the query snapshot stale.
                    path.write_text(json.dumps({key: value + 'edited' for key, value in before.items()}))
                    search.add_to_index(path)
                    after = {'sn1:1.1': 'a b ', 'sn1:1.2': 'c '}
                    path.write_text(json.dumps(after))
                    for _ in range(2):
                        ok, error = search.replace_structure_segments(path, list(before))
                        self.assertTrue(ok, str(error))
                    hits = client.search(index=indices[1], query={'match_all': {}}, size=10)['hits']['hits']
                    self.assertEqual({hit['_source']['uid']: hit['_source']['segment'] for hit in hits}, after)
                    self.assertFalse(client.exists(index=indices[1], id=create_doc_id(path, 'sn1:1.3')))
            finally:
                for index in indices:
                    client.indices.delete(index=index, ignore_unavailable=True)


if __name__ == '__main__':
    unittest.main()
