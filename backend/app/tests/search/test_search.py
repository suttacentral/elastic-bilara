from pathlib import Path
from unittest.mock import Mock

from app.core.config import settings
from search.search import Search


def test_segment_prefixes_follow_indexed_file_identity():
    search = object.__new__(Search)
    search._search = Mock()
    search._scroll_search = Mock(return_value=iter([
        {"_source": {"uid": "dhp148:4", "muid": "translation-en-sujato", "main_doc_id": "range-file"}},
        {"_source": {"uid": "dhp148:4", "muid": "root-pli-ms", "main_doc_id": "root-file"}},
        {"_source": {"uid": "sn3.22:4.2", "muid": "translation-en-sujato", "main_doc_id": "single-file"}},
    ]))
    search._search.mget.return_value = {"docs": [
        {"_id": "range-file", "found": True, "_source": {"prefix": "dhp146-156"}},
        {"_id": "root-file", "found": True, "_source": {"prefix": "dhp146-156"}},
        {"_id": "single-file", "found": True, "_source": {"prefix": "sn3.22"}},
    ]}
    results = {
        "dhp148:4": {"translation-en-sujato": "for life ends in death. ", "root-pli-ms": "pali"},
        "sn3.22:4.2": {"translation-en-sujato": "for life ends in death. "},
    }
    assert search.get_segment_prefixes(results) == {
        "dhp148:4": {"translation-en-sujato": "dhp146-156", "root-pli-ms": "dhp146-156"},
        "sn3.22:4.2": {"translation-en-sujato": "sn3.22"},
    }
    assert search._search.mget.call_count == 1


def test_empty_results_do_not_query_file_prefixes():
    search = object.__new__(Search)
    search._search = Mock()
    search._scroll_search = Mock()
    assert search.get_segment_prefixes({}) == {}
    search._scroll_search.assert_not_called()
    search._search.mget.assert_not_called()


def test_update_indexes_excludes_root_metadata_files(mocker, tmp_path: Path):
    mocker.patch.object(settings, "WORK_DIR", tmp_path)
    metadata_path = tmp_path / "_project-v2.json"
    segment_path = tmp_path / "translation" / "en" / "test.json"
    search = object.__new__(Search)
    search._process_data = Mock()

    search.update_indexes("main", "segments", [metadata_path, segment_path])

    search._process_data.assert_called_once_with(
        "main", "segments", [segment_path], False
    )
