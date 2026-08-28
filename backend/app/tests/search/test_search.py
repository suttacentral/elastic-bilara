from pathlib import Path
from unittest.mock import Mock

from app.core.config import settings
from search.search import Search


def test_update_indexes_excludes_root_metadata_files(mocker, tmp_path: Path):
    mocker.patch.object(settings, "WORK_DIR", tmp_path)
    metadata_path = tmp_path / "_project-v2.json"
    segment_path = tmp_path / "translation" / "en" / "test.json"
    search = Search.__new__(Search)
    search._process_data = Mock()

    search.update_indexes("main", "segments", [metadata_path, segment_path])

    search._process_data.assert_called_once_with(
        "main", "segments", [segment_path], False
    )
