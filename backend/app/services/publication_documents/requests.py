"""Track the GitHub request that owns the submitted document ledger."""
import time
from urllib.parse import urlparse

from github import Github, GithubException
from requests.exceptions import RequestException

from app.core.config import settings
from app.services.git.github_pull_requests import GithubPullRequests
from app.services.publication_documents.store import DocumentStore
from app.services.publications.errors import PublicationError

REQUEST_REFRESH_SECONDS = 30


def submission(state):
    if state.get("submission"):
        return state["submission"]
    # Existing ledgers predate explicit request identities. Migrate their last PR.
    job = state.get("publish") or {}
    url = job.get("url", "")
    path = urlparse(url).path.rstrip("/").split("/")
    if state.get("submitted") and len(path) >= 2 and path[-2] == "pull" and path[-1].isdigit():
        return {"number": int(path[-1]), "url": url, "state": "open", "checked_at": 0}
    return None


def request_outdated(state, uid, current_revision, published_revision):
    request = submission(state)
    target = state.get("submitted", {}).get(uid)
    return bool(request and request["state"] == "open" and target
                and target["revision"] != published_revision and target["revision"] != current_revision)


def refresh_request(work, number):
    store = DocumentStore(work, number)
    with store.locked():
        request = submission(store.read())
    if not request or request["state"] == "merged":
        return
    if time.time() - request["checked_at"] < REQUEST_REFRESH_SECONDS:
        return
    # Network I/O must not hold the checkout lock or interrupt a draft save.
    try:
        github = Github(settings.GITHUB_TOKEN, per_page=100, timeout=10, retry=0)
        pull = GithubPullRequests(github, settings.GITHUB_REPO).get(request["number"])
        state_name = "merged" if pull.merged else pull.state
    except (GithubException, RequestException) as exc:
        raise PublicationError(503, "Unable to refresh the pull request status. Please retry.") from exc
    with store.locked():
        state = store.read()
        current = submission(state)
        # Do not overwrite another refresh or a new request completed during the query.
        if current != request:
            return
        state["submission"] = {**current, "state": state_name, "checked_at": time.time()}
        job = state.get("publish")
        if job and job.get("url") == current["url"]:
            job["request_state"] = state_name
        store.write(state)
