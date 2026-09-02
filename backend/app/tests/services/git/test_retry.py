from app.services.git import retry as github_retry


def test_primary_rate_limit_retries_one_second_after_reset():
    delay = github_retry.rate_limit_retry_delay(
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1725160000"},
        now=1725159880,
    )

    assert delay == 121


def test_retry_after_takes_precedence_over_reset_time():
    delay = github_retry.rate_limit_retry_delay(
        {
            "Retry-After": "90",
            "X-RateLimit-Reset": "1725160000",
        },
        now=1725159880,
    )

    assert delay == 90


def test_only_server_side_github_failures_use_generic_retry():
    assert github_retry.is_retryable_github_status(503)
    assert not github_retry.is_retryable_github_status(422)
    assert not github_retry.is_retryable_github_status(403)
