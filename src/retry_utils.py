"""Centralized retry configuration."""
from tenacity import retry, stop_after_attempt, wait_exponential


def standard_retry():
    """
    Standard retry decorator for API calls.
    - 3 attempts
    - Exponential backoff: 2s, 4s, 10s
    - Reraises exceptions after final attempt
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )


def api_retry_no_reraise():
    """
    API retry decorator that doesn't reraise.
    Used for provider error handling where we want to catch and log.
    - 3 attempts
    - Exponential backoff: 2s, 4s, 10s
    - Does not reraise (provider handles errors)
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=False
    )
