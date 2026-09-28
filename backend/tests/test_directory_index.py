"""Directory index integration tests, isolated in a disposable PostgreSQL schema."""

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select, text

from app.core.config import settings
from app.db import database
from app.db.models.directory_index import DirectoryIndexEntry, DirectoryIndexState
from app.services.directories.index import DirectoryIndex, create_indexed_directory


class DirectoryIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_engine = database.engine
        cls.schema = f"test_directory_index_{uuid4().hex}"
        with cls.original_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.engine = cls.original_engine.execution_options(schema_translate_map={None: cls.schema})
        for model in (DirectoryIndexState, DirectoryIndexEntry):
            model.__table__.create(cls.engine)

    @classmethod
    def tearDownClass(cls):
        with cls.original_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'unpublished'
        self.root.mkdir()
        for target, value in ((database, self.engine), (settings, self.root)):
            name = 'engine' if target is database else 'WORK_DIR'
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.index = DirectoryIndex()

    def directory(self, path):
        target = self.root / path
        target.mkdir(parents=True, exist_ok=True)
        return target

    def search(self, name='', exact=False):
        return {path.relative_to(self.root).as_posix() for path in self.index.search(name, exact)}

    def test_search_preserves_name_matching_and_indexes_empty_directories(self):
        for path in ('translation/en/Tester', 'comment/en/tester-extra',
                     'root/pli/ms/tester/empty', 'tag/pli/ms/100%_done'):
            self.directory(path)
        self.assertEqual(self.search('TESTER'), {
            'translation/en/Tester', 'comment/en/tester-extra', 'root/pli/ms/tester',
        })
        self.assertEqual(self.search('Tester', exact=True), {'translation/en/Tester'})
        self.assertEqual(self.search('tester', exact=True), {'root/pli/ms/tester'})
        self.assertEqual(self.search('empty'), {'root/pli/ms/tester/empty'})
        self.assertEqual(self.search('translation/en'), set())
        self.assertEqual(self.search('%_'), {'tag/pli/ms/100%_done'})
        self.assertEqual(self.search('translation', exact=True), set())

    def test_build_excludes_hidden_nontext_and_symlink_directories(self):
        self.directory('translation/en/tester')
        self.directory('.git/tester')
        self.directory('unrelated/tester')
        self.directory('translation/.private/tester')
        (self.root / 'translation/linked').symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.search('tester'), {'translation/en/tester'})
        self.assertNotIn('translation/linked', self.search())

    def test_repeated_and_empty_searches_do_not_walk_the_filesystem(self):
        self.index.rebuild()
        with patch('app.services.directories.index.os.scandir', side_effect=AssertionError('rescanned')):
            self.assertEqual(self.search('nobody'), set())
            self.assertEqual(DirectoryIndex().search('nobody'), [])
        self.directory('translation/en/tester')
        self.index.rebuild()
        with patch('app.services.directories.index.os.scandir', side_effect=AssertionError('rescanned')):
            self.assertEqual(self.search('tester'), {'translation/en/tester'})

    def test_creation_updates_ancestors_without_rescanning_other_projects(self):
        self.directory('root/pli/ms/unchanged')
        self.index.rebuild()
        parent = self.root / 'translation/en/new'
        child = parent / 'sutta/mn'
        with patch.object(DirectoryIndex, '_walk', side_effect=AssertionError('rescanned')):
            with self.index.changes([parent, child]):
                child.mkdir(parents=True)
        self.assertTrue({'translation/en', 'translation/en/new', 'translation/en/new/sutta',
                         'translation/en/new/sutta/mn', 'root/pli/ms/unchanged'} <= self.search())

    def test_delete_removes_descendants_but_preserves_similarly_named_siblings(self):
        removed = self.directory('translation/en/100%_done/sutta')
        self.directory('translation/en/100%_done-extra/sutta')
        self.index.rebuild()
        with self.index.changes([removed.parent], recursive=True):
            shutil.rmtree(removed.parent)
        self.assertEqual(self.search('100%_done'), {'translation/en/100%_done-extra'})
        self.assertNotIn('translation/en/100%_done/sutta', self.search())

    def test_git_style_refresh_removes_missing_ancestors_and_adds_new_subtrees(self):
        old = self.directory('translation/en/old/sutta')
        self.directory('translation/fr/keep')
        self.index.rebuild()
        new = self.root / 'translation/de/new/sutta'
        with self.index.changes([old, new], recursive=True):
            shutil.rmtree(old.parent.parent)
            new.mkdir(parents=True)
        self.assertNotIn('translation/en', self.search())
        self.assertIn('translation/de/new/sutta', self.search())
        self.assertIn('translation/fr/keep', self.search())

    def test_partial_creation_is_indexed_even_when_the_operation_raises(self):
        self.index.rebuild()
        intended = self.root / 'translation/en/tester/sutta'
        with self.assertRaisesRegex(OSError, 'interrupted'):
            with self.index.changes([intended]):
                intended.parent.mkdir(parents=True)
                raise OSError('interrupted')
        self.assertEqual(self.search('tester'), {'translation/en/tester'})
        self.assertNotIn('translation/en/tester/sutta', self.search())

    def test_failed_index_update_leaves_dirty_state_for_next_reader(self):
        self.index.rebuild()
        target = self.root / 'translation/en/new'
        with patch.object(self.index, '_synchronize', side_effect=RuntimeError('update failed')):
            with self.assertRaisesRegex(RuntimeError, 'update failed'):
                with self.index.changes([target]):
                    target.mkdir(parents=True)
        self.assertEqual(DirectoryIndex().search('new'), [target])

    def test_operation_and_index_update_failures_preserve_context_and_allow_recovery(self):
        self.index.rebuild()
        intended = self.root / 'translation/en/tester/sutta'
        operation_error = OSError('interrupted')
        synchronization_error = RuntimeError('update failed')
        with patch.object(self.index, '_synchronize', side_effect=synchronization_error):
            with self.assertRaises(RuntimeError) as raised:
                with self.index.changes([intended]):
                    intended.parent.mkdir(parents=True)
                    raise operation_error
        self.assertIs(raised.exception, synchronization_error)
        self.assertIs(raised.exception.__context__, operation_error)
        self.assertFalse(raised.exception.__suppress_context__)

        ready = select(DirectoryIndexState.ready).where(
            DirectoryIndexState.work_directory == self.index.key,
        )
        with self.engine.connect() as connection:
            self.assertIs(connection.scalar(ready), False)

        reader = DirectoryIndex()
        with patch.object(reader, '_rebuild', wraps=reader._rebuild) as rebuild:
            self.assertEqual(set(reader.search('')), {
                self.root / 'translation/en', intended.parent,
            })
            rebuild.assert_called_once()
        with self.engine.connect() as connection:
            self.assertIs(connection.scalar(ready), True)

    def test_readers_wait_for_in_progress_mutations(self):
        self.index.rebuild()
        target = self.root / 'translation/en/new'
        started = threading.Event()

        def read():
            started.set()
            return DirectoryIndex().search('new')

        with ThreadPoolExecutor() as executor:
            with self.index.changes([target]):
                target.mkdir(parents=True)
                result = executor.submit(read)
                self.assertTrue(started.wait(5))
                with self.assertRaises(TimeoutError):
                    result.result(timeout=0.1)
            self.assertEqual(result.result(timeout=5), [target])

    def test_another_process_sees_committed_updates(self):
        self.index.rebuild()
        create_indexed_directory(self.root / 'translation/en/shared')
        script = '''
import json, sys
from pathlib import Path
from app.db import database
from app.services.directories.index import DirectoryIndex
database.engine = database.engine.execution_options(schema_translate_map={None: sys.argv[2]})
index = DirectoryIndex(Path(sys.argv[1]))
print(json.dumps([str(p.relative_to(index.root)) for p in index.search('shared')]))
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.root), self.schema],
                                check=True, capture_output=True, text=True, timeout=15)
        self.assertEqual(json.loads(result.stdout), ['translation/en/shared'])

    def test_reader_recovers_after_writer_process_exits_before_synchronization(self):
        self.index.rebuild()
        script = '''
import os, sys
from pathlib import Path
from app.db import database
from app.services.directories.index import DirectoryIndex
database.engine = database.engine.execution_options(schema_translate_map={None: sys.argv[2]})
index = DirectoryIndex(Path(sys.argv[1]))
target = index.root / 'translation/en/interrupted'
with index.changes([target]):
    target.mkdir(parents=True)
    os._exit(0)
'''
        subprocess.run([sys.executable, '-c', script, str(self.root), self.schema],
                       check=True, capture_output=True, text=True, timeout=15)
        self.assertEqual(self.search('interrupted'), {'translation/en/interrupted'})

    def test_symlinked_work_root_uses_the_same_index(self):
        alias = self.root.parent / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.index.rebuild()
        with patch.object(settings, 'WORK_DIR', alias):
            create_indexed_directory(alias / 'translation/en/tester')
            self.assertEqual(DirectoryIndex().search('tester'), [self.root / 'translation/en/tester'])

    def test_rebuild_discovers_external_changes_and_removes_old_entries(self):
        old = self.directory('translation/en/old')
        self.index.rebuild()
        shutil.rmtree(old)
        new = self.directory('translation/en/new')
        self.index.rebuild()
        self.assertEqual(self.search('old'), set())
        self.assertEqual(self.index.search('new'), [new])

    def test_two_web_workers_initialize_schema_and_rebuild_at_startup(self):
        self.directory('translation/en/tester')
        schema = f"test_directory_startup_{uuid4().hex}"
        with self.original_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        script = '''
import json, sys
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from app.core.config import settings
from app.db import database
from search.search import Search
settings.WORK_DIR = Path(sys.argv[1])
database.engine = create_engine(database.engine.url, connect_args={'options': '-c search_path=' + sys.argv[2]})
database.SessionLocal.configure(bind=database.engine)
with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
    from app.main import app
    from fastapi.testclient import TestClient
    from app.services.directories.index import DirectoryIndex
    with patch.object(DirectoryIndex, 'rebuild', autospec=True, side_effect=DirectoryIndex.rebuild) as rebuild:
        with TestClient(app):
            rebuild.assert_called_once()
            print(json.dumps([str(p.relative_to(settings.WORK_DIR)) for p in DirectoryIndex().search('tester')]))
'''
        processes = []
        try:
            for _ in range(2):
                processes.append(subprocess.Popen(
                    [sys.executable, '-c', script, str(self.root), schema],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ))
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertEqual(json.loads(stdout), ['translation/en/tester'])
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            with self.original_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))

    @staticmethod
    def load_services():
        from search.search import Search
        with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
            from app.services.directories import utils, remover
            from app.services.projects import utils as projects
            from app.services.git.manager import GitManager
        return utils, remover, projects, GitManager

    def test_directory_creation_and_removal_entrypoints_update_index(self):
        utils, remover, _, _ = self.load_services()
        self.index.rebuild()
        paths = {self.root / 'root/pli/ms/new', self.root / 'translation/en/tester/new'}
        with patch.object(utils, 'can_create_root_dir', return_value=True), patch.object(
            utils, 'get_matches', return_value=paths,
        ):
            self.assertTrue(utils.create_directory(Path('root/pli/ms/new')))
        self.assertEqual(len(self.search('new')), 2)
        removal = remover.Remover(SimpleNamespace(), next(iter(paths)))
        removal._delete_elements(paths)
        self.assertEqual(self.search('new'), set())

    def test_project_creation_and_first_translation_save_update_index(self):
        _, _, projects, _ = self.load_services()
        from app.services.projects.virtual_projects import VirtualProjectFile
        source = self.directory('root/pli/ms/sutta') / 'mn1_root-pli-ms.json'
        source.write_text(json.dumps({'mn1:1': 'Source'}))
        self.index.rebuild()
        target = self.root / 'translation/en/created/sutta/mn1_translation-en-created.json'
        self.assertTrue(projects.create_project_file(source, target))
        self.assertEqual(self.search('created'), {'translation/en/created'})

        virtual_target = self.root / 'translation/en/virtual/sutta/mn1_translation-en-virtual.json'
        virtual = VirtualProjectFile(source, 'root-pli-ms', virtual_target, 'translation-en-virtual', 'mn1')
        user = SimpleNamespace(github_id=1)
        with patch.object(projects.search, 'add_to_index', return_value=(True, None)), patch.object(
            projects, 'get_user', return_value=user,
        ), patch.object(projects, '_schedule_file_commit', return_value='task'):
            self.assertEqual(projects.materialize_translation_file(virtual, {'mn1:1': 'Text'}, user),
                             (True, None, 'task', True))
        self.assertEqual(self.search('virtual'), {'translation/en/virtual'})

    def test_tag_creation_updates_index(self):
        self.load_services()
        from app.api.api_v1.endpoints import tags
        source = self.directory('root/pli/ms/sutta/new') / 'mn1_root-pli-ms.json'
        source.write_text(json.dumps({'mn1:1': 'Source'}))
        self.index.rebuild()
        with patch.object(tags.search, 'get_file_paths', return_value={str(source)}), patch.object(
            tags.search, 'add_to_index', return_value=(True, None),
        ):
            asyncio.run(tags.create_tag_data_file(SimpleNamespace(), 'mn1'))
        self.assertEqual(self.search('new'), {'root/pli/ms/sutta/new', 'tag/pli/ms/sutta/new'})

    def git_repositories(self):
        from pygit2 import clone_repository, init_repository, Signature
        _, _, _, GitManager = self.load_services()
        remote_path = self.root.parent / 'remote'
        remote = init_repository(remote_path, initial_head='unpublished')
        source = remote_path / 'root/pli/ms/initial/test.json'
        source.parent.mkdir(parents=True)
        source.write_text('{}')
        signature = Signature('Test', 'test@example.com')

        def commit(repo):
            repo.index.add_all()
            repo.index.write()
            repo.create_commit('HEAD', signature, signature, 'Test change', repo.index.write_tree(),
                               [] if repo.head_is_unborn else [repo.head.target])

        commit(remote)
        checkout = clone_repository(str(remote_path), self.root)
        manager = GitManager.__new__(GitManager)
        manager.unpublished = checkout
        manager.author = manager.committer = signature
        self.index.rebuild()
        return remote, manager, commit

    def test_git_fast_forward_reconciles_added_and_removed_directories(self):
        remote, manager, commit = self.git_repositories()
        shutil.rmtree(Path(remote.workdir) / 'root/pli/ms/initial')
        target = Path(remote.workdir) / 'translation/en/remote/test.json'
        target.parent.mkdir(parents=True)
        target.write_text('{}')
        commit(remote)
        manager.pull(manager.unpublished)
        self.assertEqual(self.search('remote'), {'translation/en/remote'})
        self.assertEqual(self.search('initial'), set())

    def test_git_merge_reconciles_remote_directory_changes(self):
        remote, manager, commit = self.git_repositories()
        local = self.directory('translation/en/local') / 'test.json'
        local.write_text('{}')
        commit(manager.unpublished)
        self.index.rebuild()
        target = Path(remote.workdir) / 'comment/en/remote/test.json'
        target.parent.mkdir(parents=True)
        target.write_text('{}')
        commit(remote)
        manager.pull(manager.unpublished)
        self.assertEqual(self.search('remote'), {'comment/en/remote'})
        self.assertEqual(self.search('local'), {'translation/en/local'})

    def test_git_force_refreshes_index_even_when_commit_has_not_changed(self):
        _, manager, _ = self.git_repositories()
        target = self.root / 'root/pli/ms/initial'
        with self.index.changes([target], recursive=True):
            shutil.rmtree(target)
        self.assertEqual(self.search('initial'), set())
        manager.pull(manager.unpublished, force=True)
        self.assertEqual(self.search('initial'), {'root/pli/ms/initial'})

    def test_search_api_keeps_response_permissions_counts_and_sorting(self):
        # Import the real endpoint without creating/populating Elasticsearch.
        from search.search import Search
        with patch.object(Search, '_create_index'), patch.object(Search, '_populate_index'):
            from app.api.api_v1.endpoints import directories
        parent = self.directory('translation/en/tester')
        self.directory('translation/en/tester/child')
        self.directory('comment/en/tester')
        (parent / 'test.json').write_text('{}')
        self.index.rebuild()
        with patch.object(directories, 'get_publish_permissions', return_value={'translation-en-tester': True}):
            result = directories.search_path_tree('TESTER', SimpleNamespace(github_id=1))
        self.assertEqual(result['total_matches'], 2)
        self.assertEqual([m['path'] for m in result['matches']], [
            'comment/en/tester/', 'translation/en/tester/',
        ])
        self.assertEqual(result['matches'][1], {
            'path': 'translation/en/tester/', 'name': 'tester',
            'parent_tree': ['translation/', 'translation/en/'], 'depth': 3,
            'child_directories': 1, 'child_files': 1, 'total_children': 2,
        })
        self.assertEqual(result['statistics'], {'min_depth': 3, 'max_depth': 3, 'avg_depth': 3})
        self.assertEqual(result['publish_permissions'], {'translation-en-tester': True})


if __name__ == '__main__':
    unittest.main()
