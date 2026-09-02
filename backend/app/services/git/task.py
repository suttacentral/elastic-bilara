import logging
import time

from celery import Task
from github import GithubException
from github.GithubException import RateLimitExceededException
from pygit2 import GitError

from app.services.git import retry as github_retry

logger = logging.getLogger(__name__)


class GitTask(Task):
    retryable_exceptions = (OSError, ConnectionError, TimeoutError, GitError)
    max_retries = 15
    initial_backoff = 0.1098
    backoff_factor = 2

    def __call__(self, *args, **kwargs):
        try:
            return super().__call__(*args, **kwargs)
        except RateLimitExceededException as exc:
            countdown = github_retry.rate_limit_retry_delay(exc.headers, time.time())
            logger.warning(
                "GitHub rate limit reached; retrying task %s in %.1f seconds (remaining=%s, reset=%s)",
                self.request.id,
                countdown,
                exc.headers.get("x-ratelimit-remaining"),
                exc.headers.get("x-ratelimit-reset"),
            )
            self.retry(
                exc=exc,
                countdown=countdown,
                max_retries=self.max_retries,
            )
        except GithubException as exc:
            if not github_retry.is_retryable_github_status(exc.status):
                raise
            self._retry_with_backoff(exc)
        except self.retryable_exceptions as exc:
            self._retry_with_backoff(exc)

    def _retry_with_backoff(self, exc: Exception) -> None:
        retry_count = self.request.retries
        backoff = self.initial_backoff * (self.backoff_factor**retry_count)
        self.retry(exc=exc, countdown=backoff, max_retries=self.max_retries)
