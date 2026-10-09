"""Produce the legacy compatibility record without using it as editing state."""
from copy import deepcopy

COMMON_FIELDS = (
    "publication_number", "root_lang_iso", "root_lang_name", "translation_lang_iso",
    "translation_lang_name", "source_url", "text_uid", "translation_title",
    "translation_subtitle", "root_title", "is_published", "publication_status", "pitaka",
)
LICENSE_FIELDS = ("license_type", "license_abbreviation", "license_url", "license_statement")
EDITION_FIELDS = ("edition_number", "publisher", "publication_type")


def _authors(entry, result):
    uids = entry.get("creator_uid", "")
    names = entry.get("creator_name", "")
    if "author_uid" not in result and "collaborator" not in result:
        if isinstance(uids, list):
            # v2 has no team identifier. Use the stable publication identifier for
            # a newly generated legacy team, never an arbitrarily selected author.
            result["author_uid"] = entry["publication_number"]
            result["collaborator"] = [
                {"collaborator_uid": uid, "author_name": name, "author_github_handle": ""}
                for uid, name in zip(uids, names)
            ]
        else:
            result.update(author_uid=uids, author_name=names,
                          author_github_handle=deepcopy(entry.get("creator_github_handle", "")))
        return

    # Existing legacy identities and membership are historical data. Only exact,
    # unique UIDs establish a correspondence; names and list positions do not.
    authors = dict(zip(uids, names)) if isinstance(uids, list) else {uids: names}
    if "collaborator" in result:
        collaborators = result["collaborator"]
        if isinstance(collaborators, list):
            for uid, name in authors.items():
                matches = [c for c in collaborators if isinstance(c, dict) and uid
                           and c.get("collaborator_uid") == uid]
                if len(matches) == 1:
                    matches[0]["author_name"] = name
        # GitHub editing accounts have no author correspondence in v2.
        return
    uid = result.get("author_uid")
    if uid and uid in authors:
        result["author_name"] = authors[uid]
        if not isinstance(uids, list) and "creator_github_handle" in entry:
            result["author_github_handle"] = deepcopy(entry["creator_github_handle"])


def _editions(entry, result):
    if "edition" not in result or result["edition"] == []:
        result["edition"] = [{
            "edition_number": entry.get("edition_number", "1"),
            "publisher": entry.get("publisher", "SuttaCentral"),
            "publication_type": entry.get("publication_type", "website"),
            "publication_date": entry.get("first_published", entry.get("publication_date", "")),
            "edition_url": entry.get("editions_url", ""),
        }]
        return
    editions = result["edition"]
    # v2 has no edition identity or URL-item selector. Multiple historical
    # editions and link arrays cannot be mapped and are preserved verbatim.
    if not isinstance(editions, list) or len(editions) != 1 or not isinstance(editions[0], dict):
        return
    edition = editions[0]
    for field in EDITION_FIELDS:
        if field in entry:
            edition[field] = entry[field]
    if "first_published" in entry or "publication_date" in entry:
        edition["publication_date"] = entry.get("first_published", entry.get("publication_date"))
    url = edition.get("edition_url", edition.get("url", ""))
    if "editions_url" in entry and isinstance(url, str):
        edition["edition_url"] = entry["editions_url"]
        edition.pop("url", None)


def to_legacy(entry, legacy=None):
    result = deepcopy(legacy) if legacy is not None else {}
    for field in COMMON_FIELDS:
        if field in entry:
            result[field] = deepcopy(entry[field])
    for source, target in (("creation_process", "translation_process"), ("text_description", "translation_description")):
        if source in entry:
            result[target] = entry[source]
    license_fields = {field: entry[field] for field in LICENSE_FIELDS if field in entry}
    if license_fields and ("license" not in result or isinstance(result["license"], dict)):
        result.setdefault("license", {}).update(license_fields)
    _authors(entry, result)
    _editions(entry, result)
    return result
