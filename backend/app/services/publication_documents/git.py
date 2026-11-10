"""Read immutable published blobs and publish selected documents without checking out branches."""
from pathlib import Path

from pygit2 import Blob, Commit, Index, IndexEntry, Repository

from app.services.publication_documents.store import revision
from app.services.publications.errors import PublicationError


def published_commit(published):
    repo = Repository(str(published))
    for ref in ("refs/remotes/origin/published", "refs/heads/published"):
        try:
            return repo, repo.lookup_reference(ref).peel(Commit)
        except KeyError:
            continue
    raise PublicationError(409, "The published Git baseline is unavailable.")


def blob_content(commit, path):
    try:
        blob = commit.tree[path]
    except KeyError:
        raise PublicationError(409, f"No published baseline exists for {path}.") from None
    if not isinstance(blob, Blob) or blob.filemode == 0o120000:
        raise PublicationError(403, "Only regular published HTML files are supported.")
    try:
        return blob.data.decode("utf-8")
    except UnicodeError as exc:
        raise PublicationError(422, "Published HTML must be UTF-8 encoded.") from exc


def baseline(published, path):
    _, commit = published_commit(published)
    content = blob_content(commit, path)
    return {"content": content, "revision": revision(content), "commit": str(commit.id)}


def publish_documents(manager, number, job, contents, previous=None):
    """Build from remote trees. No shared working tree or index is modified."""
    from app.services.git.manager import GitManager

    repo = manager.published
    repo.remotes["origin"].fetch(prune=True)
    published = repo.lookup_reference("refs/remotes/origin/published").peel(Commit)
    for uid, target in job["documents"].items():
        current = blob_content(published, target["path"])
        current_revision = revision(current)
        if current_revision == target["revision"]:
            continue
        if current_revision != target["base_revision"]:
            raise PublicationError(409, f"Published content changed for {Path(target['path']).name}. Review it before publishing.")
    prefix = f"publication-documents-{number}-"
    open_prs = manager.pull_requests.list_open()
    matches = [(name, pr) for name, pr in open_prs.items() if name.startswith(prefix)]
    if len(matches) > 1:
        raise PublicationError(409, "Multiple document pull requests are open. Resolve them before submitting another release.")
    branch, pull_request = matches[0] if matches else (prefix + job["generation"], None)
    try:
        parent = repo.lookup_reference(f"refs/remotes/origin/{branch}").peel(Commit)
    except KeyError:
        parent = published
    changed = {uid: target for uid, target in job["documents"].items()
               if revision(blob_content(parent, target["path"])) != target["revision"]}
    # A previous delivery may have pushed this branch but failed before creating
    # the PR. An unchanged remote branch still needs that final API operation.
    if not changed and (pull_request or parent.tree.id == published.tree.id):
        return {"url": pull_request.html_url if pull_request else "",
                "request_number": pull_request.number if pull_request else None,
                "message": "The selected content already matches the publication target."}
    tree = Index()
    tree.read_tree(parent.tree)
    for uid, target in changed.items():
        path = target["path"]
        branch_revision = revision(blob_content(parent, path))
        allowed = {revision(blob_content(published, path)), target["revision"]}
        if (pull_request and previous and previous.get("request_number") == pull_request.number
                and uid in previous.get("documents", {})):
            allowed.add(previous["documents"][uid]["revision"])
        if branch_revision not in allowed:
            raise PublicationError(409, f"The pull request contains other edits to {Path(path).name}. Review them before updating it.")
        mode = parent.tree[path].filemode
        tree.add(IndexEntry(path, repo.create_blob(contents[uid].encode("utf-8")), mode))
    tree_id = tree.write_tree(repo)
    if tree_id != parent.tree.id:
        commit_id = repo.create_commit(None, manager.author, manager.committer,
                                      f"Update publication documents for {number}", tree_id, [parent.id])
    else:
        commit_id = parent.id
    # A concurrent remote update is rejected by the non-force push.
    local_ref = repo.references.create(f"refs/heads/{branch}", commit_id, force=True)
    try:
        GitManager.push(repo, branch=branch, force=False)
    finally:
        # Only the push needs a local ref. Retries rebuild it from remote trees.
        local_ref.delete()
    pull_request = pull_request or manager.pull_requests.create(
        title=f"Publication documents for {number}",
        body=f"Document changes reviewed and submitted from Bilara by {manager.user.username}.",
        head=f"{manager.repo_owner}:{branch}",
    )
    return {"url": pull_request.html_url, "request_number": pull_request.number,
            "message": "Pull request submitted. Publication requires review and merge."}
