"""Submit the two synced metadata files as one pull request."""
import fcntl

from pygit2 import Blob, Commit, Index, IndexEntry

from app.services.git.manager import GitManager
from app.services.publications.errors import PublicationError
from app.services.publications.service import PublicationService
from app.services.publications.store import PUBLICATION_FILES, PublicationStore

BRANCH = "publication-metadata"


def require_publishable(service):
    service.require_admin()
    with service.store.locked():
        state = service.store.read_sync()
        if state and state["status"] != "synced":
            raise PublicationError(409, "Wait for metadata to sync to unpublished before publishing.")


def publish_metadata(work, published, github_id):
    from app.services.users.utils import get_user

    # Serialize repeated clicks and task retries without locking metadata saves.
    store = PublicationStore(work)
    store.directory.mkdir(parents=True, exist_ok=True)
    with (store.directory / "publish.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            # Both permissions and sync state may change while waiting for the lock.
            user = get_user(github_id)
            service = PublicationService(work, user)
            require_publishable(service)
            manager = GitManager(published, work, user)
            return _publish_metadata(manager)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _publish_metadata(manager):
    repo = manager.published
    repo.remotes["origin"].fetch(prune=True)
    published = repo.lookup_reference("refs/remotes/origin/published").peel(Commit)
    source = repo.lookup_reference("refs/remotes/origin/unpublished").peel(Commit)
    pull_request = manager.pull_requests.list_open().get(BRANCH)
    tree = Index()
    tree.read_tree(published.tree)
    for path in PUBLICATION_FILES:
        try:
            blob = source.tree[path]
        except KeyError:
            raise PublicationError(409, f"{path} is missing from unpublished.") from None
        if not isinstance(blob, Blob) or blob.filemode != 0o100644:
            raise PublicationError(409, f"{path} must be a regular metadata file.")
        tree.add(IndexEntry(path, blob.id, blob.filemode))
    tree_id = tree.write_tree(repo)
    if tree_id == published.tree.id and not pull_request:
        return ""

    try:
        parent = repo.lookup_reference(f"refs/remotes/origin/{BRANCH}").peel(Commit)
    except KeyError:
        parent = published
    # Reuse an unchanged submission only if merging it into the current base
    # still publishes the exact requested tree. Base metadata may have changed.
    # Matching published takes precedence: clear obsolete PR changes below.
    if pull_request and tree_id != published.tree.id and all(
        path in parent.tree and parent.tree[path].id == source.tree[path].id
        and parent.tree[path].filemode == source.tree[path].filemode
        for path in PUBLICATION_FILES
    ):
        merged = repo.merge_commits(published, parent)
        if merged.conflicts is None and merged.write_tree(repo) == tree_id:
            return pull_request.html_url
    # A normally merged PR branch is already contained in published. Starting
    # there keeps a single parent and still fast-forwards the retained branch.
    if parent.id != published.id and repo.descendant_of(published.id, parent.id):
        parent = published
    parents = [parent.id]
    # Include the current base so an updated/reused PR contains only metadata,
    # even after unrelated published changes or a previous squash merge.
    if parent.id != published.id and not repo.descendant_of(parent.id, published.id):
        parents.append(published.id)
    if tree_id != parent.tree.id or len(parents) > 1:
        commit_id = repo.create_commit(None, manager.author, manager.committer,
                                      "Update publication metadata", tree_id, parents)
        local_ref = repo.references.create(f"refs/heads/{BRANCH}", commit_id, force=True)
        try:
            GitManager.push(repo, branch=BRANCH, force=False)
        finally:
            local_ref.delete()
    # Clear the old changes before closing the PR. A failed close must remain
    # retryable instead of reporting success and leaving an empty PR open.
    if tree_id == published.tree.id:
        manager.pull_requests.close(pull_request)
        return ""
    # A retry after a successful push still needs to create the PR.
    pull_request = pull_request or manager.pull_requests.create(
        title="Update publication metadata",
        body=f"Metadata submitted from Bilara by {manager.user.username}.\n\n"
             "Updates _publication-v2.json and _publication.json. Please review and merge manually.",
        head=f"{manager.repo_owner}:{BRANCH}",
        base="published",
    )
    return pull_request.html_url
