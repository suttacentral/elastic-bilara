"""Infrastructure-independent tests of the production structure engine."""
import tempfile
import fcntl
import unittest
from pathlib import Path

from app.services.projects.structure_engine import build_preview, apply_edits, load_rules
from app.services.projects.structure_store import StructureStore, StructureConflict
from unittest.mock import patch


class StructureTests(unittest.TestCase):
    def files(self):
        return {
            'root/pli/ms/dn1_root-pli-ms.json': {'dn1:1.1': 'A ', 'dn1:1.2': 'B ', 'dn1:1.3': 'C '},
            'comment/en/u/dn1_comment-en-u.json': {'dn1:1.1': 'A ', 'dn1:1.2': 'B ', 'dn1:1.3': 'C '},
            'html/pli/ms/dn1_html-pli-ms.json': {'dn1:1.1': '<p>{}', 'dn1:1.2': '{}', 'dn1:1.3': '{}</p>'},
        }

    def preview(self, files=None, operation='merge', uid='dn1:1.1'):
        files = files or self.files()
        return build_preview(files, next(iter(files)), operation, uid, load_rules(operation))

    def test_merge_uses_type_separator_only_at_merge_point(self):
        p = self.preview()
        self.assertEqual(p['projects'][0]['data'], {'dn1:1.1': 'A B ', 'dn1:1.2': 'C '})
        self.assertEqual(p['projects'][1]['data'], {'dn1:1.1': 'A | B ', 'dn1:1.2': 'C '})

    def test_empty_values_do_not_change_merge_target(self):
        files = self.files()
        files['translation/en/u/dn1_translation-en-u.json'] = {'dn1:1.1': 'X', 'dn1:1.2': '', 'dn1:1.3': '', 'dn1:2.1': 'Y'}
        with self.assertRaises(ValueError):  # Unknown root UID must not silently disappear.
            self.preview(files)
        files[next(iter(files))]['dn1:2.1'] = 'D '
        p = self.preview(files)
        self.assertEqual(p['mergee_uid'], 'dn1:1.2')
        self.assertEqual(p['projects'][-1]['data']['dn1:2.1'], 'Y')

    def test_split_final_segment_and_integer_carry(self):
        files = {'root/pli/ms/dn1_root-pli-ms.json': {'dn1:1.18': 'A', 'dn1:1.19': 'B'}}
        p = self.preview(files, 'split', 'dn1:1.18')
        self.assertEqual(p['projects'][0]['data'], {'dn1:1.18': 'A', 'dn1:1.19': '', 'dn1:1.20': 'B'})
        p = self.preview(files, 'split', 'dn1:1.19')
        self.assertEqual(p['projects'][0]['data']['dn1:1.20'], '')

    def test_unknown_type_rejected(self):
        files = self.files()
        files['foo/x/dn1_foo-x.json'] = {}
        with self.assertRaisesRegex(ValueError, 'merge.json'):
            self.preview(files)

    def test_single_level_split_and_merge_use_colon_as_number_boundary(self):
        root = 'root/pli/ms/an1.1_root-pli-ms.json'
        files = {root: {'an1.1:9': 'A', 'an1.1:10': 'B', 'an1.1:11': 'C'}}
        p = self.preview(files, 'split', 'an1.1:9')
        self.assertEqual(p['projects'][0]['data'], {
            'an1.1:9': 'A', 'an1.1:10': '', 'an1.1:11': 'B', 'an1.1:12': 'C'})
        p = self.preview(files, 'merge', 'an1.1:9')
        self.assertEqual(p['projects'][0]['data'], {'an1.1:9': 'AB', 'an1.1:10': 'C'})
        self.assertFalse(p['merge_crosses_section'])
        self.assertEqual(self.preview(files, 'split', 'an1.1:11')['splitter_uid'], 'an1.1:12')
        with self.assertRaisesRegex(ValueError, 'no next root segment'):
            self.preview(files, 'merge', 'an1.1:11')

    def test_cross_section_merge_follows_root_order_and_only_shifts_target_section(self):
        for anchor, target, following, unrelated in [
            ('dn1:1.9', 'dn1:2.1', 'dn1:2.2', 'dn1:20.1'),
            ('dn1:1.1.9', 'dn1:1.2.0', 'dn1:1.2.1', 'dn1:1.20.1'),
        ]:
            with self.subTest(anchor=anchor):
                files = {
                    'root/pli/ms/dn1_root-pli-ms.json': {anchor: 'A', target: '', following: 'C', unrelated: 'D'},
                    'comment/en/u/dn1_comment-en-u.json': {anchor: 'X', target: 'Y', following: 'Z'},
                }
                p = self.preview(files, 'merge', anchor)
                self.assertEqual(p['mergee_uid'], target)
                self.assertTrue(p['merge_crosses_section'])
                self.assertEqual(p['projects'][0]['data'], {anchor: 'A', target: 'C', unrelated: 'D'})
                self.assertEqual(p['projects'][1]['data'], {anchor: 'X| Y', target: 'Z', unrelated: ''})

    def test_merge_single_segment_section_preserves_content_in_anchor(self):
        files = {'root/pli/ms/dn1_root-pli-ms.json': {'dn1:1.9': 'A', 'dn1:2.1': 'B'}}
        p = self.preview(files, 'merge', 'dn1:1.9')
        self.assertTrue(p['merge_crosses_section'])
        self.assertEqual(p['projects'][0]['data'], {'dn1:1.9': 'AB'})

    def test_manual_confirmation_and_edits_are_required(self):
        p = self.preview()
        with self.assertRaises(ValueError):
            apply_edits(p, {}, [])
        html = p['manual_projects'][0]
        result = apply_edits(p, {html: {'dn1:1.1': '<p>{}'}}, [html])
        self.assertEqual(result[html]['dn1:1.1'], '<p>{}')
        with self.assertRaises(ValueError):
            apply_edits(p, {html: {'dn1:9.9': 'bad'}}, [html])

    def test_exact_section_boundaries_and_sparse_files(self):
        files = {'root/pli/ms/dn1_root-pli-ms.json': {'dn1:1.1': 'A', 'dn1:1.2': 'B', 'dn1:10.1': 'C'}, 'reference/pli/ms/dn1_reference-pli-ms.json': {'dn1:10.1': 'ref'}}
        p = self.preview(files, 'split')
        self.assertEqual(p['projects'][0]['data']['dn1:10.1'], 'C')
        self.assertEqual(p['projects'][1]['data']['dn1:10.1'], 'ref')
        self.assertEqual(p['projects'][1]['data']['dn1:1.2'], '')


class StoreTests(unittest.TestCase):
    def test_shared_locks_allow_readers_and_exclude_writers(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StructureStore(Path(directory) / 'work', Path(directory) / 'work/root.json')
            for shared in (True, False):
                with self.subTest(shared=shared), store.lock(shared=shared):
                    with (store.directory / 'lock').open('a+') as reader:
                        if shared:
                            fcntl.flock(reader, fcntl.LOCK_SH | fcntl.LOCK_NB)
                        else:
                            with self.assertRaises(BlockingIOError):
                                fcntl.flock(reader, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    with (store.directory / 'lock').open('a+') as writer:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with (store.directory / 'lock').open('a+') as writer:
                    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_interrupted_commit_can_be_resumed_without_repeating_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'unpublished'
            root = work / 'root/dn1_root-pli-ms.json'
            root.parent.mkdir(parents=True)
            root.write_text('{"dn1:1.1":"A"}')
            other = work / 'translation/dn1_translation-en-u.json'
            other.parent.mkdir()
            other.write_text('{"dn1:1.1":"B"}')
            store = StructureStore(work, root)
            before = store.revision()
            record = {'operation_id': '00000000-0000-0000-0000-000000000001', 'fingerprint': 'test',
                      'files': {str(root.relative_to(work)): {'dn1:1.1': 'A', 'dn1:1.2': ''}, str(other.relative_to(work)): {'dn1:1.1': 'B', 'dn1:1.2': ''}}}
            with store.lock():
                store.prepare(record)
                with self.assertRaises(StructureConflict):
                    store.check_ready()
                original = store.write_json
                def fail_other(path, value):
                    if path == other:
                        raise OSError('disk failure')
                    return original(path, value)
                with patch.object(store, 'write_json', side_effect=fail_other):
                    with self.assertRaises(OSError):
                        store.apply(record)
                store.apply(record)
                store.finish(record, {'ok': True})
                store.check_ready()
                self.assertNotEqual(before, store.revision())
                self.assertEqual(store.get(record['operation_id'])['result'],
                                 {'ok': True, 'structure_revision': store.revision()})
                with self.assertRaises(StructureConflict):
                    store.check_revision(before)


if __name__ == '__main__':
    unittest.main()
