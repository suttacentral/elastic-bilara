import difflib
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from app.services.publication_documents.catalog import confined_path, load_catalog
from app.services.publication_documents.git import baseline
from app.services.publication_documents.requests import refresh_request, request_outdated, submission
from app.services.publication_documents.store import DocumentStore, read_html, revision
from app.services.publication_documents.validation import scan, validate
from app.services.publications.errors import PublicationError
from app.services.publications.service import PublicationService
from app.services.git.checkout import checkout_lock


def new_job(user, documents):
    return {"generation": str(uuid4()), "user": {key: value for key, value in user.model_dump().items()
            if key in ("github_id", "username", "email", "avatar_url", "role")},
            "documents": documents, "status": "pending", "task_id": None, "dispatch_after": 0, "error": ""}


def job_status(job):
    if not job:
        return {"status": "idle", "can_retry": False}
    return {key: job.get(key) for key in ("status", "task_id", "error", "url", "message", "request_state")} | {
        "can_retry": job["status"] == "failed",
        "documents": {uid: target["revision"] for uid, target in job["documents"].items()},
    }


class DocumentService:
    def __init__(self, work, published, user):
        self.work = Path(work)
        self.published = Path(published)
        self.user = user
        self.publications = PublicationService(work, user)

    def _store(self, number, operation="sync"):
        self.publications.get(number)
        return DocumentStore(self.work, number, operation)

    def _catalog(self, number):
        self.publications.get(number)
        catalog = load_catalog(self.work)
        return {uid: doc for uid, doc in catalog.items() if number in doc["publications"]}

    def _document(self, number, uid, catalog=None):
        documents = self._catalog(number) if catalog is None else catalog
        if uid not in documents:
            raise PublicationError(404, "Document not found in this publication.")
        doc = documents[uid]
        # Shared physical files require permission for every publication that owns them.
        for owner in doc["publications"]:
            self.publications.get(owner)
        path = confined_path(self.work, doc["path"], html=True)
        if not path.is_file():
            raise PublicationError(409, "The document is missing from unpublished. Restore it before editing.")
        return doc, path

    def counts(self):
        with checkout_lock(self.work):
            allowed = {e["publication_number"] for e in self.publications.list()}
            counts = dict.fromkeys(allowed, 0)
            for doc in load_catalog(self.work).values():
                if doc["publications"] <= allowed:
                    for number in doc["publications"]:
                        counts[number] += 1
            return counts

    def list(self, number):
        publication = self.publications.get(number)
        store = self._store(number)
        refresh_request(self.work, number)
        with store.locked():
            catalog = self._catalog(number)
            state = store.read()
            results = []
            for uid in catalog:
                doc, path = self._document(number, uid, catalog)
                content = read_html(path)
                headings = scan(content).headings
                title = next((h["title"] for h in headings if h["level"] == 1), doc["filename"])
                released = baseline(self.published, doc["path"])
                results.append({"id": uid, "filename": doc["filename"], "title": title,
                                "path": doc["path"], "editions": doc["editions"],
                                "revision": revision(content), "changed": content != released["content"],
                                "request_outdated": request_outdated(state, uid, revision(content), released["revision"]),
                                "bytes": len(content.encode("utf-8"))})
            return {"publication": {key: publication.get(key) for key in (
                "publication_number", "translation_title", "creator_name", "translation_lang_iso")},
                    "documents": results, "sync": job_status(state["sync"]), "publish": job_status(state["publish"])}

    def _validation(self, doc, content):
        def relative_link(path, anchor):
            raw = Path(doc["path"]).parent / unquote(path)
            try:
                target = confined_path(self.work, raw, html=True)
            except PublicationError:
                return f"Unsupported relative document link: {path}"
            if not target.is_file():
                return f"Linked document does not exist: {path}"
            if anchor and anchor not in scan(read_html(target)).ids:
                return f"No anchor #{anchor} exists in {path}."
            return None
        return validate(content, relative_link=relative_link)

    def get(self, number, uid):
        self._document(number, uid)
        refresh_request(self.work, number)
        return self._get(number, uid)

    def _get(self, number, uid):
        store = self._store(number)
        with store.locked():
            doc, path = self._document(number, uid)
            content = read_html(path)
            released = baseline(self.published, doc["path"])
            state = store.read()
            base_revision = state["documents"].get(uid, {}).get("base_revision", released["revision"])
            if content == released["content"]:
                base_revision = released["revision"]
            return {"id": uid, "filename": doc["filename"], "path": doc["path"], "editions": doc["editions"],
                    "content": content, "revision": revision(content), "base_revision": base_revision,
                    "published_content": released["content"], "published_revision": released["revision"],
                    "published_changed": base_revision != released["revision"] and content != released["content"],
                    "request_outdated": request_outdated(state, uid, revision(content), released["revision"]),
                    "validation": self._validation(doc, content),
                    "sync": job_status(state["sync"]), "publish": job_status(state["publish"])}

    def check(self, number, uid, content):
        doc, _ = self._document(number, uid)
        return self._validation(doc, content)

    def diff(self, number, uid, content, comparison):
        doc, path = self._document(number, uid)
        before = read_html(path) if comparison == "saved" else baseline(self.published, doc["path"])["content"]
        return {"diff": "".join(difflib.unified_diff(before.splitlines(keepends=True), content.splitlines(keepends=True),
                    fromfile=f"{comparison}/{doc['filename']}", tofile=f"draft/{doc['filename']}"))}

    def save(self, number, uid, body):
        store = self._store(number)
        with store.locked():
            doc, path = self._document(number, uid)
            current = read_html(path)
            if revision(current) != body.revision:
                raise PublicationError(409, "This document changed. Reload it before saving; your edits have been kept in the editor.")
            released = baseline(self.published, doc["path"])
            if body.published_revision != released["revision"]:
                raise PublicationError(409, "The published version changed. Reload and review the comparison before saving.")
            validation = self._validation(doc, body.content)
            if not validation["can_save"]:
                raise PublicationError(422, {"message": "Unsafe HTML cannot be saved.", "validation": validation})
            state = store.read()
            if current != body.content:
                base_revision = state["documents"].get(uid, {}).get("base_revision", released["revision"])
                # A draft starting from published content belongs to a new editing cycle.
                if current == released["content"]:
                    base_revision = released["revision"]
                state["documents"][uid] = {"path": doc["path"], "base_revision": base_revision}
                previous_sync = state["sync"]
                targets = dict(previous_sync["documents"]) if previous_sync and previous_sync["status"] != "synced" else {}
                targets[uid] = {"path": doc["path"], "revision": revision(body.content), "base_revision": base_revision}
                state["sync"] = new_job(self.user, targets)
                store.save(doc["path"], body.content, state)
            return self._get(number, uid)

    def acknowledge_baseline(self, number, uid, body):
        store = self._store(number)
        with store.locked():
            doc, path = self._document(number, uid)
            released = baseline(self.published, doc["path"])
            if revision(read_html(path)) != body.revision or released["revision"] != body.published_revision:
                raise PublicationError(409, "The document changed again. Reload before acknowledging the published version.")
            state = store.read()
            state["documents"][uid] = {"path": doc["path"], "base_revision": released["revision"]}
            store.write(state)
            return self._get(number, uid)

    def status(self, number):
        self.publications.get(number)
        refresh_request(self.work, number)
        return self._status(number)

    def _status(self, number):
        store = self._store(number)
        with store.locked():
            state = store.read()
            catalog = self._catalog(number)
            documents = {}
            for uid in catalog:
                doc, path = self._document(number, uid, catalog)
                content = read_html(path)
                released = baseline(self.published, doc["path"])
                documents[uid] = {"revision": revision(content), "changed": content != released["content"],
                                  "request_outdated": request_outdated(state, uid, revision(content), released["revision"])}
            return {"sync": job_status(state["sync"]), "publish": job_status(state["publish"]),
                    "documents": documents}

    def retry(self, number, operation):
        self.publications.get(number)
        store = self._store(number, operation)
        with store.locked():
            job = store.read_sync()
            if not job or job["status"] != "failed":
                raise PublicationError(409, "There is no failed operation to retry.")
            for uid in job["documents"]:
                self._document(number, uid)
            job.update(status="pending", task_id=None, dispatch_after=0, error="")
            store.write_sync(job)
        return self._status(number)

    def publish(self, number, selection):
        store = self._store(number)
        refresh_request(self.work, number)
        with store.locked():
            state = store.read()
            if state["publish"] and state["publish"]["status"] not in ("synced", "failed"):
                raise PublicationError(409, "A publication request is already in progress.")
            targets = {}
            for item in selection:
                detail = self._get(number, item.id)
                if detail["revision"] != item.revision or detail["published_revision"] != item.published_revision:
                    raise PublicationError(409, "A selected document changed. Reload and review before publishing.")
                if detail["published_changed"]:
                    raise PublicationError(409, "Review and acknowledge the updated published version before submitting.")
                if not detail["validation"]["valid"]:
                    raise PublicationError(422, {"message": f"Resolve validation errors in {detail['filename']} before publishing.",
                                                 "validation": detail["validation"]})
                if detail["content"] == detail["published_content"] and not detail["request_outdated"]:
                    continue
                targets[item.id] = {"path": detail["path"], "revision": detail["revision"],
                                    "base_revision": detail["published_revision"]}
            if not targets:
                raise PublicationError(409, "No selected document differs from the published version.")
            job = new_job(self.user, targets)
            request = submission(state)
            if request:
                state["submission"] = request
            job["previous"] = {"documents": state.get("submitted", {}),
                               "request_number": request["number"] if request else None}
            state["publish"] = job
            store.write(state)
            return self._status(number)
