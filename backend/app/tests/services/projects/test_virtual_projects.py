import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.projects import virtual_projects
from app.services.projects.virtual_projects import resolve_virtual_file


class StubFileIndex:
    def __init__(self, paths_by_muid: dict[str, set[str]]):
        self.paths_by_muid = paths_by_muid
        self.calls = []

    def get_file_paths(
        self,
        muid: str,
        prefix: str | None = None,
        exact: bool = False,
        _type: str = "root_path",
    ) -> set[str]:
        self.calls.append((muid, prefix, exact, _type))
        return self.paths_by_muid.get(muid, set())


def _write_project_config(work_dir: Path, entries: list[dict[str, str]]) -> None:
    (work_dir / "_project-v2.json").write_text(
        json.dumps(entries),
        encoding="utf-8",
    )


def _project_entry(
    root_path: str = "root/pli/ms/sutta",
    translation_path: str = "translation/en/tester/sutta",
    translation_muid: str = "translation-en-tester",
) -> dict[str, str]:
    return {
        "root_path": root_path,
        "translation_path": translation_path,
        "translation_muids": translation_muid,
    }


@pytest.mark.parametrize("translation_path", ["", "."])
def test_project_mappings_allow_work_directory_without_comment_mapping(
    tmp_path, translation_path,
):
    _write_project_config(tmp_path, [_project_entry(translation_path=translation_path)])

    mappings = virtual_projects._load_project_mappings(
        tmp_path / "_project-v2.json", 0, 0, tmp_path,
    )

    assert len(mappings) == 1
    assert mappings[0].target_path == tmp_path


@pytest.mark.parametrize(
    "translation_path",
    [
        "translation/en/tester/sutta",
        "./translation/en/tester/sutta",
        "other/../translation/en/tester/sutta",
        "absolute",
    ],
)
def test_comment_mapping_uses_resolved_translation_path(tmp_path, translation_path):
    if translation_path == "absolute":
        translation_path = str(tmp_path / "translation/en/tester/sutta")
    _write_project_config(tmp_path, [_project_entry(translation_path=translation_path)])

    mappings = virtual_projects._load_project_mappings(
        tmp_path / "_project-v2.json", 0, 0, tmp_path,
    )

    assert [(mapping.target_path, mapping.target_muid) for mapping in mappings] == [
        (tmp_path / "translation/en/tester/sutta", "translation-en-tester"),
        (tmp_path / "comment/en/tester/sutta", "comment-en-tester"),
    ]


def test_project_mappings_cache_resolved_paths_until_config_changes(
    tmp_path,
    monkeypatch,
):
    work_dir = tmp_path / "unpublished"
    (work_dir / "root/pli/ms/sutta").mkdir(parents=True)
    _write_project_config(work_dir, [_project_entry()])
    monkeypatch.setattr(settings, "WORK_DIR", work_dir)

    configured_path = virtual_projects._configured_path
    configured_paths = []

    def record_configured_path(*args):
        configured_paths.append(args[0])
        return configured_path(*args)

    monkeypatch.setattr(
        virtual_projects,
        "_configured_path",
        record_configured_path,
    )

    virtual_projects._project_mappings()
    virtual_projects._project_mappings()

    assert configured_paths == [
        "root/pli/ms/sutta",
        "translation/en/tester/sutta",
        "comment/en/tester/sutta",
    ]

    _write_project_config(
        work_dir,
        [
            _project_entry(),
            _project_entry(
                root_path="root/en/site/sutta",
                translation_path="translation/fr/tester/sutta",
                translation_muid="translation-fr-tester",
            ),
        ],
    )

    mappings = virtual_projects._project_mappings()

    assert len(mappings) == 4
    assert configured_paths == [
        "root/pli/ms/sutta",
        "translation/en/tester/sutta",
        "comment/en/tester/sutta",
        "root/pli/ms/sutta",
        "translation/en/tester/sutta",
        "comment/en/tester/sutta",
        "root/en/site/sutta",
        "translation/fr/tester/sutta",
        "comment/fr/tester/sutta",
    ]


def test_cached_project_mappings_reflect_root_directory_changes(
    tmp_path,
    monkeypatch,
):
    work_dir = tmp_path / "unpublished"
    work_dir.mkdir(exist_ok=True)
    _write_project_config(work_dir, [_project_entry()])
    monkeypatch.setattr(settings, "WORK_DIR", work_dir)
    translation_path = work_dir / "translation/en/tester/sutta"
    translation_parent = translation_path.parent
    root_path = work_dir / "root/pli/ms/sutta"

    assert virtual_projects.is_virtual_directory(translation_path) is False
    assert virtual_projects.list_virtual_directories(translation_parent) == []

    root_path.mkdir(parents=True)

    assert virtual_projects.is_virtual_directory(translation_path) is True
    assert virtual_projects.list_virtual_directories(translation_parent) == ["sutta/"]

    root_path.rmdir()

    assert virtual_projects.is_virtual_directory(translation_path) is False
    assert virtual_projects.list_virtual_directories(translation_parent) == []


def test_resolve_virtual_file_uses_file_index_without_recursive_scan(
    tmp_path,
    monkeypatch,
):
    work_dir = tmp_path / "unpublished"
    source_path = work_dir / "root/pli/ms/sutta/mn/mn1_root-pli-ms.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(json.dumps({"mn1:1.1": "Source"}), encoding="utf-8")
    _write_project_config(
        work_dir,
        [
            {
                "root_path": "root/pli/ms/sutta",
                "translation_path": "translation/en/tester/sutta",
                "translation_muids": "translation-en-tester",
            }
        ],
    )
    file_index = StubFileIndex({"root-pli-ms": {str(source_path)}})
    monkeypatch.setattr(settings, "WORK_DIR", work_dir)

    def fail_recursive_scan(*_args, **_kwargs):
        raise AssertionError("recursive scan is not allowed")

    monkeypatch.setattr(Path, "rglob", fail_recursive_scan)

    result = resolve_virtual_file("translation-en-tester", "mn1", file_index)

    assert result is not None
    assert result.source_path == source_path
    assert result.target_path == (
        work_dir
        / "translation/en/tester/sutta/mn/mn1_translation-en-tester.json"
    )
    assert file_index.calls == [
        ("root-pli-ms", "mn1", True, "file_path"),
    ]


def test_resolve_virtual_file_preserves_conflict_detection(tmp_path, monkeypatch):
    work_dir = tmp_path / "unpublished"
    first_source = work_dir / "root/pli/ms/sutta/mn/mn1_root-pli-ms.json"
    second_source = work_dir / "root/en/site/sutta/mn/mn1_root-en-site.json"
    for source_path in (first_source, second_source):
        source_path.parent.mkdir(parents=True)
        source_path.write_text(
            json.dumps({"mn1:1.1": "Source"}),
            encoding="utf-8",
        )
    _write_project_config(
        work_dir,
        [
            {
                "root_path": "root/pli/ms/sutta",
                "translation_path": "translation/en/tester/sutta",
                "translation_muids": "translation-en-tester",
            },
            {
                "root_path": "root/en/site/sutta",
                "translation_path": "translation/en/tester/sutta",
                "translation_muids": "translation-en-tester",
            },
        ],
    )
    file_index = StubFileIndex(
        {
            "root-pli-ms": {str(first_source)},
            "root-en-site": {str(second_source)},
        }
    )
    monkeypatch.setattr(settings, "WORK_DIR", work_dir)

    with pytest.raises(ValueError, match="Conflicting virtual translation file"):
        resolve_virtual_file("translation-en-tester", "mn1", file_index)


def test_resolve_virtual_file_ignores_mapping_with_missing_root(
    tmp_path,
    monkeypatch,
):
    work_dir = tmp_path / "unpublished"
    work_dir.mkdir(exist_ok=True)
    _write_project_config(work_dir, [_project_entry()])
    monkeypatch.setattr(settings, "WORK_DIR", work_dir)
    missing_source = work_dir / "root/pli/ms/sutta/mn/mn1_root-pli-ms.json"
    file_index = StubFileIndex({"root-pli-ms": {str(missing_source)}})

    result = resolve_virtual_file("translation-en-tester", "mn1", file_index)

    assert result is None
    assert file_index.calls == []
