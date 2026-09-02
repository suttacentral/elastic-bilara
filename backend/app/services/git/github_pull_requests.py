from github import Github
from github.PullRequest import PullRequest


class GithubPullRequests:
    def __init__(self, github: Github, repository_name: str) -> None:
        self._repository_name = repository_name
        self._repository = github.get_repo(repository_name, lazy=True)

    def list_open(self, base: str = "published") -> dict[str, PullRequest]:
        pull_requests = self._repository.get_pulls(state="open", base=base)
        return {
            pull_request.head.ref: pull_request
            for pull_request in pull_requests
            if pull_request.head.repo is not None
            and pull_request.head.repo.full_name == self._repository_name
        }

    def create(
        self, title: str, body: str, head: str, base: str = "published"
    ) -> PullRequest:
        return self._repository.create_pull(
            title=title, body=body, base=base, head=head
        )

    @staticmethod
    def close(pull_request: PullRequest) -> None:
        pull_request.edit(state="closed")
