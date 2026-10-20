"""Recover a complete tag batch and its sync intent before exposing any files."""
import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.services.git.checkout import checkout_lock
from app.services.storage import storage_errors, write_json


def is_tag_path(path):
    """Whether a checkout-relative path belongs to tag definitions or passages."""
    path = Path(path)
    return path == Path("_tags.json") or path.parts[:1] == ("tag",)


class TagError(ValueError):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class TagStore:
    def __init__(self, work):
        self.work = Path(work).resolve()
        self.directory = self.work.parent / ".tag-operations" / self.work.name
        self.journal = self.directory / "pending.json"
        self.sync_path = self.directory / "sync.json"

    @contextmanager
    def locked(self):
        with checkout_lock(self.work):
            self.recover()
            yield self

    def read_json(self, path, default=None):
        with storage_errors():
            if not path.exists():
                return default
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise TagError(409, f"Invalid JSON in {path.name}. Repair the file before editing tags.") from exc

    def read_tags(self):
        tags = self.read_json(self.work / "_tags.json", [])
        if (not isinstance(tags, list) or any(
                not isinstance(tag, dict) or not isinstance(tag.get("tag"), str) for tag in tags)):
            raise TagError(409, "Invalid tag definitions. Repair _tags.json before editing tags.")
        if len({tag["tag"] for tag in tags}) != len(tags):
            raise TagError(409, "Duplicate tag definitions. Repair _tags.json before editing tags.")
        return tags

    def read_sync(self):
        return self.read_json(self.sync_path)

    def write_sync(self, state):
        write_json(self.sync_path, state)

    def target(self, relative):
        path = self.work / relative
        if (path.resolve() != path or not path.is_relative_to(self.work)
                or not (relative == "_tags.json" or (
                    relative.startswith("tag/") and relative.endswith("_tag.json")))):
            raise TagError(409, "Invalid path in tag operation.")
        return path

    def recover(self):
        pending = self.read_json(self.journal)
        if pending is not None:
            targets = {name: self.target(name) for name in pending["files"]}
            self._apply(pending, targets)

    def save(self, files, user, message):
        if not files:
            return self.read_sync()
        targets = {name: self.target(name) for name in files}
        previous = self.read_sync()
        paths = set(files)
        if previous and previous["status"] != "synced":
            paths.update(previous["paths"])
        state = {
            "generation": str(uuid4()), "status": "pending", "task_id": None,
            "paths": sorted(paths), "message": message,
            "user": {key: user[key] for key in ("github_id", "username", "email", "avatar_url", "role")},
            "dispatch_after": 0, "error": "",
        }
        pending = {"files": files, "sync": state}
        with storage_errors():
            self.directory.mkdir(parents=True, exist_ok=True)
        # The durable intent comes first. Recovery replays the entire batch,
        # including its outbox, even after a crash between file replacements.
        write_json(self.journal, pending)
        self._apply(pending, targets)
        return state

    def _apply(self, pending, targets):
        """Apply a batch whose targets were all checked under the checkout lock."""
        for name, data in pending["files"].items():
            write_json(targets[name], data)
        self.write_sync(pending["sync"])
        write_json(self.journal, None)
