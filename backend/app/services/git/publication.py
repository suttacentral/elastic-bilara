from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.git import utils

if TYPE_CHECKING:
    from github.PullRequest import PullRequest


@dataclass(frozen=True)
class PublicationPlan:
    target_branch: str
    target_pull_request: PullRequest | None = None
    pull_requests_to_close: tuple[PullRequest, ...] = ()


def build_publication_plan(
    paths: list[Path],
    open_pull_requests: dict[str, PullRequest],
    project_pull_request_paths: set[Path] | frozenset[Path] = frozenset(),
) -> PublicationPlan:
    if not paths:
        raise ValueError("No file paths provided.")

    project_branch = utils.get_project_head(paths[0])
    if len(paths) == 1:
        project_pull_request = open_pull_requests.get(project_branch)
        if project_pull_request and paths[0] in project_pull_request_paths:
            return PublicationPlan(project_branch, project_pull_request)
        file_branch = next(iter(utils.get_file_heads(paths).values()))
        return PublicationPlan(file_branch, open_pull_requests.get(file_branch))

    file_pull_requests = tuple(
        open_pull_requests[file_branch]
        for file_branch in utils.get_file_heads(paths).values()
        if file_branch in open_pull_requests
    )
    return PublicationPlan(
        target_branch=project_branch,
        target_pull_request=open_pull_requests.get(project_branch),
        pull_requests_to_close=file_pull_requests,
    )
