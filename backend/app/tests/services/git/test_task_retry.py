from time import monotonic
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


@pytest.mark.parametrize("outcome", ["success", "worker_lost"])
def test_metadata_publication_acknowledges_completion_or_requeues_worker_loss(monkeypatch, outcome):
    from billiard.einfo import ExceptionInfo
    from billiard.exceptions import WorkerLostError
    from celery.worker.request import Request
    from app.tasks import publish_publication_metadata

    task = publish_publication_metadata
    ack, reject, failed = Mock(), Mock(), Mock()
    monkeypatch.setattr(task.backend, "mark_as_failure", failed)
    message = Mock(headers={"id": "metadata-delivery-test", "task": task.name},
                   body=([123], {}, {}), delivery_info={}, properties={})
    request = Request(message, app=task.app, task=task, decoded=True,
                      on_ack=ack, on_reject=reject)
    request.on_accepted(1234, monotonic())
    ack.assert_not_called()
    reject.assert_not_called()

    if outcome == "success":
        request.on_success((False, "https://example.org/pull/1", 0))
        ack.assert_called_once()
        reject.assert_not_called()
    else:
        try:
            raise WorkerLostError("worker process exited")
        except WorkerLostError:
            info = ExceptionInfo()
        request.on_failure(info, return_ok=True)
        ack.assert_not_called()
        reject.assert_called_once()
        assert reject.call_args.args[-1] is True  # Requeue the unacknowledged delivery.
    failed.assert_not_called()
