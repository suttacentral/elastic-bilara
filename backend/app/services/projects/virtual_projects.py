import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from search.utils import get_muid, get_prefix, muid_from_relative_path


class ProjectFileIndex(Protocol):
    def get_file_paths(
        self,
        muid: str,
        prefix: str | None = None,
        exact: bool = False,
        _type: str = "root_path",
    ) -> set[str]: ...


@dataclass(frozen=True)
class VirtualProjectFile:
    source_path: Path
    source_muid: str
    target_path: Path
    target_muid: str
    prefix: str

    def as_directory_entry(self) -> dict[str, str]:
        work_dir = settings.WORK_DIR.resolve()
        return {
            "name": self.target_path.name,
            "target_path": self.target_path.relative_to(work_dir).as_posix(),
            "target_muid": self.target_muid,
            "source_path": self.source_path.relative_to(work_dir).as_posix(),
            "source_muid": self.source_muid,
            "prefix": self.prefix,
        }


@dataclass(frozen=True)
class ProjectMapping:
    root_path: Path
    translation_path: Path
    translation_muid: str


def _configured_path(value: str, work_dir: Path) -> Path:
    path = (work_dir / value).resolve()
    try:
        path.relative_to(work_dir)
    except ValueError:
        raise ValueError(f"Configured project path is outside the work directory: {value}")
    return path


@lru_cache(maxsize=8)
def _load_project_entries(
    project_file: Path,
    modified_ns: int,
    size: int,
) -> tuple[dict, ...]:
    del modified_ns, size
    with project_file.open(encoding="utf-8") as file:
        return tuple(json.load(file))


@lru_cache(maxsize=8)
def _load_project_mappings(
    project_file: Path,
    modified_ns: int,
    size: int,
    work_dir: Path,
) -> tuple[ProjectMapping, ...]:
    entries = _load_project_entries(project_file, modified_ns, size)
    mappings = []
    for entry in entries:
        root_path = _configured_path(entry["root_path"], work_dir)
        translation_path = _configured_path(entry["translation_path"], work_dir)
        translation_muid = entry["translation_muids"]
        if not translation_muid:
            continue
        mappings.append(
            ProjectMapping(
                root_path,
                translation_path,
                translation_muid,
            )
        )
    return tuple(mappings)


def _natural_key(value: str) -> list[tuple[int, int | str]]:
    return [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
    ]


def _project_mappings() -> tuple[ProjectMapping, ...]:
    work_dir = settings.WORK_DIR.resolve()
    project_file = work_dir / "_project-v2.json"
    if not project_file.is_file():
        return ()
    project_stat = project_file.stat()
    return _load_project_mappings(
        project_file,
        project_stat.st_mtime_ns,
        project_stat.st_size,
        work_dir,
    )


def list_virtual_files(directory: Path) -> list[VirtualProjectFile]:
    virtual_files: dict[str, VirtualProjectFile] = {}
    for mapping in _project_mappings():
        try:
            relative_directory = directory.relative_to(mapping.translation_path)
        except ValueError:
            continue

        source_directory = mapping.root_path / relative_directory
        if not source_directory.is_dir():
            continue

        for source_path in source_directory.iterdir():
            if not source_path.is_file() or source_path.suffix != ".json":
                continue
            prefix = get_prefix(source_path)
            target_path = directory / f"{prefix}_{mapping.translation_muid}.json"
            if target_path.exists():
                continue
            candidate = VirtualProjectFile(
                source_path=source_path,
                source_muid=get_muid(source_path),
                target_path=target_path,
                target_muid=mapping.translation_muid,
                prefix=prefix,
            )
            existing = virtual_files.get(target_path.name)
            if existing and existing.source_path != candidate.source_path:
                raise ValueError(f"Conflicting virtual translation file: {target_path}")
            virtual_files[target_path.name] = candidate

    return sorted(virtual_files.values(), key=lambda item: _natural_key(item.target_path.name))


def is_virtual_directory(directory: Path) -> bool:
    for mapping in _project_mappings():
        try:
            relative_directory = directory.relative_to(mapping.translation_path)
        except ValueError:
            try:
                mapping.translation_path.relative_to(directory)
            except ValueError:
                continue
            if mapping.root_path.is_dir():
                return True
            continue
        if (mapping.root_path / relative_directory).is_dir():
            return True
    return False


def list_virtual_directories(directory: Path) -> list[str]:
    names = set()
    for mapping in _project_mappings():
        try:
            relative_directory = directory.relative_to(mapping.translation_path)
        except ValueError:
            try:
                remaining = mapping.translation_path.relative_to(directory)
            except ValueError:
                continue
            if not mapping.root_path.is_dir():
                continue
            if remaining.parts:
                candidate = directory / remaining.parts[0]
                if not candidate.is_dir():
                    names.add(f"{remaining.parts[0]}/")
            continue

        source_directory = mapping.root_path / relative_directory
        if not source_directory.is_dir():
            continue
        for source_child in source_directory.iterdir():
            if source_child.is_dir() and not (directory / source_child.name).is_dir():
                names.add(f"{source_child.name}/")
    return sorted(names, key=_natural_key)


def _source_muid(mapping: ProjectMapping) -> str:
    relative_root = mapping.root_path.relative_to(settings.WORK_DIR.resolve())
    source_muid = muid_from_relative_path(relative_root.as_posix())
    if not source_muid:
        raise ValueError(
            f"Configured root path does not identify a source project: {relative_root}"
        )
    return source_muid


def resolve_virtual_file(
    target_muid: str,
    prefix: str,
    file_index: ProjectFileIndex,
) -> VirtualProjectFile | None:
    candidates: dict[Path, VirtualProjectFile] = {}
    indexed_paths_by_muid: dict[str, set[str]] = {}
    for mapping in _project_mappings():
        if mapping.translation_muid != target_muid:
            continue
        if not mapping.root_path.is_dir():
            continue
        source_muid = _source_muid(mapping)
        if source_muid not in indexed_paths_by_muid:
            indexed_paths_by_muid[source_muid] = file_index.get_file_paths(
                muid=source_muid,
                prefix=prefix,
                exact=True,
                _type="file_path",
            )
        for indexed_path in indexed_paths_by_muid[source_muid]:
            source_path = Path(indexed_path).resolve()
            if not source_path.is_file() or get_prefix(source_path) != prefix:
                continue
            try:
                relative_directory = source_path.parent.relative_to(mapping.root_path)
            except ValueError:
                continue
            target_path = (
                mapping.translation_path
                / relative_directory
                / f"{prefix}_{mapping.translation_muid}.json"
            )
            candidate = VirtualProjectFile(
                source_path=source_path,
                source_muid=get_muid(source_path),
                target_path=target_path,
                target_muid=mapping.translation_muid,
                prefix=prefix,
            )
            existing = candidates.get(target_path)
            if existing and existing.source_path != candidate.source_path:
                raise ValueError(f"Conflicting virtual translation file: {target_path}")
            candidates[target_path] = candidate

    if not candidates:
        return None
    if len(candidates) > 1:
        raise ValueError(f"Conflicting virtual translation project: {target_muid}/{prefix}")
    return next(iter(candidates.values()))
