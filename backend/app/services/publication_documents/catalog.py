"""Resolve document identities from edition manifests, never from client paths."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from app.services.publications.errors import PublicationError
from app.services.storage import storage_errors


def document_id(path):
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def confined_path(work, relative, *, html=False):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "_publication":
        raise PublicationError(403, "Document path is outside the publication directory.")
    if html and ("matter" not in relative.parts[1:-1] or relative.suffix.lower() != ".html"):
        raise PublicationError(403, "Only HTML files in a matter directory can be edited.")
    work = Path(work).resolve()
    target = work
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            raise PublicationError(403, "Symbolic links are not supported for publication documents.")
    if not target.resolve().is_relative_to(work / "_publication"):
        raise PublicationError(403, "Document path is outside the publication directory.")
    return target


def _references(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("frontmatter", "backmatter", "mainmatter") and isinstance(child, list):
                yield from (ref for ref in child if isinstance(ref, str))
            elif isinstance(child, (dict, list)):
                yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def load_catalog(work):
    work = Path(work).resolve()
    root = confined_path(work, "_publication")
    documents = {}
    with storage_errors():
        for config in sorted(root.rglob("*.json")):
            relative = config.relative_to(work)
            if "editions" not in relative.parts:
                continue
            confined_path(work, relative)
            try:
                entry = json.loads(config.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise PublicationError(409, f"Invalid edition configuration: {relative}") from exc
            if not isinstance(entry, dict) or not isinstance(entry.get("publication_number"), str):
                continue
            for reference in dict.fromkeys(_references(entry)):
                url = urlsplit(reference)
                if url.scheme or url.netloc or not url.path.lower().endswith(".html"):
                    continue
                # Normalize manifest-relative paths, then validate containment and symlinks.
                raw = config.parent / url.path
                if raw.is_absolute() and not raw.is_relative_to(work):
                    raise PublicationError(403, "Invalid edition document reference.")
                # Check before resolving so symlinks cannot be hidden by normalization.
                if ".." in raw.relative_to(work).parts:
                    raise PublicationError(403, "Parent traversal is not supported in edition references.")
                path = raw.relative_to(work).as_posix()
                confined_path(work, path, html=True)
                uid = document_id(path)
                document = documents.setdefault(uid, {"id": uid, "path": path, "filename": Path(path).name,
                                                     "publications": set(), "editions": []})
                document["publications"].add(entry["publication_number"])
                edition = {"publication_number": entry["publication_number"],
                           "number": str(entry.get("edition_number", "")),
                           "type": str(entry.get("publication_type", ""))}
                if edition not in document["editions"]:
                    document["editions"].append(edition)
    return documents
