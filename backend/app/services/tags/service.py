"""Validate and save tag definitions together with affected passage references."""
import os
import re
from pathlib import Path

from app.services.projects.structure_store import StructureConflict, StructureStore
from app.services.storage import storage_errors
from app.services.tags.store import TagError, TagStore, is_tag_path

TAG_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_name(name):
    if not isinstance(name, str) or not TAG_NAME_PATTERN.fullmatch(name):
        raise TagError(400, "Tag name must be lowercase alphanumeric with hyphens only.")


def rewrite_value(value, old, new):
    parts = []
    for item in value.split(","):
        if item.strip() != old:
            parts.append(item)
        elif new is not None:
            parts.append(" " * (len(item) - len(item.lstrip())) + new)
    return ",".join(parts)


def validate_segments(work, data):
    names = {tag["tag"] for tag in TagStore(work).read_tags()}
    invalid = sorted({item.strip() for value in data.values() for item in value.split(",")
                      if item.strip() and item.strip() not in names})
    if invalid:
        raise TagError(400, f"Invalid tags: {', '.join(invalid)}. Tags must be defined in the tag list.")


class TagService:
    def __init__(self, work):
        self.store = TagStore(work)

    def list(self):
        with self.store.locked():
            return self.store.read_tags()

    def _reference_changes(self, old, new):
        changes = {}
        paths = []
        tag_directory = self.store.work / "tag"

        def unreadable(error):
            raise error

        with storage_errors():
            if tag_directory.is_symlink():
                raise TagError(409, "Symlinked tag directories are not supported.")
            for directory, subdirectories, filenames in (os.walk(tag_directory, onerror=unreadable)
                                                         if tag_directory.exists() else ()):
                directory = Path(directory)
                if any((directory / name).is_symlink() for name in subdirectories):
                    raise TagError(409, "Symlinked tag directories are not supported.")
                paths.extend(directory / name for name in filenames if name.endswith("_tag.json"))
        paths.sort()
        for path in paths:
            relative = path.relative_to(self.store.work).as_posix()
            self.store.target(relative)
            data = self.store.read_json(path)
            if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
                raise TagError(409, f"Invalid tag data in {relative}. Repair the file before editing tags.")
            updated = {uid: rewrite_value(value, old, new) for uid, value in data.items()}
            if updated != data:
                changes[relative] = updated
        # An unfinished split/merge can replay older passage data. Do not let
        # it resurrect a renamed/deleted tag after this operation completes.
        with storage_errors():
            try:
                affects_tags = any(is_tag_path(path) for path in StructureStore.pending_paths(self.store.work))
            except StructureConflict as error:
                raise TagError(409, str(error)) from error
            if affects_tags:
                raise TagError(409, "A text structure operation affecting tags is pending. Resume it before editing tags.")
        return changes

    def mutate(self, operation, user, name=None, data=None):
        data = data or {}
        for field in ("tag", "expansion", "definition"):
            if field in data and not isinstance(data[field], str):
                raise TagError(422, f"{field} must be a string.")
        with self.store.locked():
            tags = self.store.read_tags()
            original = [dict(tag) for tag in tags]
            files = {}
            if operation == "create":
                new_name = data.get("tag", "").strip()
                if not new_name:
                    raise TagError(400, "Tag name is required")
                validate_name(new_name)
                if any(tag["tag"] == new_name for tag in tags):
                    raise TagError(409, f"Tag '{new_name}' already exists")
                tag = {"tag": new_name, "expansion": data.get("expansion", ""),
                       "definition": data.get("definition", "")}
                tags.append(tag)
                result = dict(tag)
                message = f"Create tag {new_name}"
            else:
                tag = next((tag for tag in tags if tag["tag"] == name), None)
                if tag is None:
                    raise TagError(404, f"Tag '{name}' not found")
                if operation == "delete":
                    files = self._reference_changes(name, None)
                    tags.remove(tag)
                    result = {"detail": f"Tag '{name}' deleted", "files_modified": len(files)}
                    message = f"Delete tag {name} and its references"
                else:
                    new_name = data.get("tag", name).strip()
                    if new_name != name:
                        validate_name(new_name)
                        if any(t["tag"] == new_name for t in tags):
                            raise TagError(409, f"Tag '{new_name}' already exists")
                        files = self._reference_changes(name, new_name)
                    tag.update({key: data[key] for key in ("expansion", "definition") if key in data})
                    tag["tag"] = new_name
                    result = dict(tag)
                    message = f"Rename tag {name} to {new_name}" if name != new_name else f"Update tag {name}"
            if tags != original:
                files["_tags.json"] = tags
            state = self.store.save(files, user.model_dump(), message)
            from app.services.tags.sync import public_status

            return {**result, "_sync": public_status(state)}
