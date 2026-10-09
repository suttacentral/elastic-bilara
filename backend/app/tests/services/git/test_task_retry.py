from unittest.mock import Mock

import pytest
from celery import Celery
from github import GithubException
from github.GithubException import RateLimitExceededException

from app.services.git.task import GitTask
from app.services.publications.errors import PublicationStorageError


class FailingGitTask(GitTask):
    def __init__(self, exception):
        self.exception = exception

    def run(self):
        raise self.exception


FailingGitTask.bind(Celery("git-task-test"))


@pytest.mark.parametrize('error_type', [OSError, PublicationStorageError])
def test_storage_failures_keep_the_existing_retry_behavior(error_type):
    exception = error_type('storage unavailable')
    task = FailingGitTask(exception)
    task.retry = Mock()

    task()

    task.retry.assert_called_once_with(exc=exception, countdown=task.initial_backoff, max_retries=task.max_retries)


def test_rate_limit_exception_retries_after_reset(monkeypatch):
    exception = RateLimitExceededException(
        403,
        {"message": "API rate limit exceeded"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1725160000"},
    )
    task = FailingGitTask(exception)
    task.retry = Mock()
    monkeypatch.setattr("app.services.git.task.time.time", lambda: 1725159880)

    task()

    task.retry.assert_called_once_with(exc=exception, countdown=121, max_retries=15)


def test_validation_error_is_not_retried():
    exception = GithubException(422, {"message": "Validation failed"}, {})
    task = FailingGitTask(exception)
    task.retry = Mock()

    with pytest.raises(GithubException) as raised:
        task()

    assert raised.value is exception
    task.retry.assert_not_called()
