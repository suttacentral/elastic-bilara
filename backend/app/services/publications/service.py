import hashlib
import json
import re
from copy import deepcopy

from app.services.publications.conversion import to_legacy
from app.services.publications.errors import PublicationError
from app.services.publications.schema import WRITER_FIELDS
from app.services.publications.store import PublicationStore
from app.services.users.utils import creator_github_handle_matches


def is_admin(user):
    return user.role in ("administrator", "superuser")


def require_access(user):
    if not user.is_active or user.role not in ("writer", "administrator", "superuser"):
        raise PublicationError(403, "An active writer or administrator account is required.")


def revision(entry):
    content = json.dumps(entry, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(content).hexdigest()


def present(entry):
    result = deepcopy(entry)
    result["_revision"] = revision(entry)
    return result


def validate_authors(entry):
    uids = entry.get("creator_uid", "")
    names = entry.get("creator_name", "")
    if isinstance(uids, list):
        if not uids or any(not uid.strip() for uid in uids) or len(set(uids)) != len(uids):
            raise PublicationError(422, "Creator UIDs must be nonempty and unique.")
        if not isinstance(names, list) or len(names) != len(uids):
            raise PublicationError(422, "Creator UIDs and names must be aligned lists.")
    elif not isinstance(names, str):
        raise PublicationError(422, "A single creator needs a single name.")
    # GitHub accounts identify editors of the publication, independently of authors.


def normalize_dates(entry, changes):
    if "first_published" in changes and "publication_date" in changes and changes["first_published"] != changes["publication_date"]:
        raise PublicationError(422, "First published and publication date must agree.")
    if "publication_date" in changes:
        entry["first_published"] = changes["publication_date"]
    elif "first_published" in changes and "publication_date" in entry:
        entry["publication_date"] = changes["first_published"]


class PublicationService:
    def __init__(self, work, user):
        require_access(user)
        self.user = user
        self.store = PublicationStore(work)

    def require_admin(self):
        if not is_admin(self.user):
            raise PublicationError(403, "Administrator permission is required.")

    def check_publish(self):
        self.require_admin()
        with self.store.locked():
            self.store.read()

    def owns(self, entry):
        return bool(self.user.username) and creator_github_handle_matches(self.user.username, entry.get("creator_github_handle"))

    def find(self, entries, number):
        entry = next((e for e in entries if e["publication_number"] == number), None)
        if entry is None or (not is_admin(self.user) and not self.owns(entry)):
            raise PublicationError(404, "Publication not found.")
        return entry

    def list(self):
        with self.store.locked():
            entries = self.store.read_v2()
            return [present(e) for e in entries if is_admin(self.user) or self.owns(e)]

    def get(self, number):
        with self.store.locked():
            entries = self.store.read_v2()
            return present(self.find(entries, number))

    def next_number(self):
        self.require_admin()
        with self.store.locked():
            entries = self.store.read_v2()
            numbers = {e["publication_number"] for e in entries}
            maximum = max((int(n[5:]) for n in numbers if re.fullmatch(r"scpub\d+", n)), default=0)
            return f"scpub{maximum + 1}"

    @staticmethod
    def check_number(number):
        if not re.fullmatch(r"scpub[1-9]\d*", number):
            raise PublicationError(422, "Publication number must be scpub followed by a positive integer.")

    def create(self, body):
        self.require_admin()
        entry = body.model_dump(exclude_unset=True)
        number = entry.get("publication_number", "")
        self.check_number(number)
        uid = entry.get("creator_uid")
        if not isinstance(uid, list) and (not isinstance(uid, str) or not uid.strip()):
            raise PublicationError(422, "Creator UID is required for a new publication.")
        normalize_dates(entry, entry.copy())
        validate_authors(entry)
        with self.store.locked():
            entries = self.store.read_v2()
            if any(e["publication_number"] == number for e in entries):
                raise PublicationError(409, "Publication number already exists.")
            legacy = self.store.read_legacy()
            if number in legacy:
                raise PublicationError(409, "The target number has compatibility history. Choose another publication number.")
            legacy[number] = to_legacy(entry)
            entries.append(entry)
            self.store.save(entries, legacy)
            return present(entry)

    def update(self, number, body):
        changes = body.changes.model_dump(exclude_unset=True)
        if not is_admin(self.user) and set(changes) - WRITER_FIELDS:
            raise PublicationError(403, "These fields are read-only: " + ", ".join(sorted(set(changes) - WRITER_FIELDS)))
        with self.store.locked():
            entries = self.store.read_v2()
            previous = self.find(entries, number)
            if body.revision != revision(previous):
                raise PublicationError(409, "This publication changed. Reload it before saving; your edits have not been applied.")
            entry = {**previous, **changes}
            new_number = entry["publication_number"]
            self.check_number(new_number)
            if new_number != number and any(e["publication_number"] == new_number for e in entries):
                raise PublicationError(409, "Publication number already exists.")
            normalize_dates(entry, changes)
            validate_authors(entry)
            legacy = self.store.read_legacy()
            if new_number != number and new_number in legacy:
                raise PublicationError(409, "The target number has compatibility history. Choose another publication number.")
            converted = to_legacy(entry, legacy.get(number))
            entries[entries.index(previous)] = entry
            if new_number != number:
                legacy.pop(number, None)
            legacy[new_number] = converted
            self.store.save(entries, legacy)
            return present(entry)

    def delete(self, number, expected_revision):
        self.require_admin()
        with self.store.locked():
            entries = self.store.read_v2()
            entry = self.find(entries, number)
            if expected_revision != revision(entry):
                raise PublicationError(409, "This publication changed. Reload before deleting.")
            legacy = self.store.read_legacy()
            entries.remove(entry)
            legacy.pop(number, None)
            self.store.save(entries, legacy)
