from collections.abc import Mapping

RATE_LIMIT_RESET_MARGIN_SECONDS = 1
SECONDARY_RATE_LIMIT_DELAY_SECONDS = 60


def rate_limit_retry_delay(headers: Mapping[str, str], now: float) -> float:
    normalized_headers = {key.lower(): value for key, value in headers.items()}

    if retry_after := normalized_headers.get("retry-after"):
        return max(float(retry_after), RATE_LIMIT_RESET_MARGIN_SECONDS)

    if reset_at := normalized_headers.get("x-ratelimit-reset"):
        return max(
            float(reset_at) - now + RATE_LIMIT_RESET_MARGIN_SECONDS,
            RATE_LIMIT_RESET_MARGIN_SECONDS,
        )

    return SECONDARY_RATE_LIMIT_DELAY_SECONDS


def is_retryable_github_status(status: int) -> bool:
    return 500 <= status < 600
