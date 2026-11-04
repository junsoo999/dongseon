"""Shared HTTP helpers: retry transient failures with exponential backoff."""

import logging
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def send_with_retry(
    send: Callable[[], httpx.Response],
    *,
    sleep: Callable[[float], None] = time.sleep,
    base_delay_s: float = 1.0,
) -> httpx.Response:
    """Call ``send`` and retry 5xx responses and timeouts, at most 3 attempts in total.

    Args:
        send: Performs one request.
        sleep: Override for tests.
        base_delay_s: First backoff delay; doubles each retry.

    Returns:
        The last response (which may still be an error response).

    Raises:
        httpx.TimeoutException: If the last attempt timed out.
        httpx.TransportError: If the last attempt failed to connect.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = send()
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == MAX_ATTEMPTS:
                raise
            logger.warning("request failed (attempt %d), retrying", attempt)
        else:
            if resp.status_code < 500 or attempt == MAX_ATTEMPTS:
                return resp
            logger.warning("HTTP %d (attempt %d), retrying", resp.status_code, attempt)
        sleep(base_delay_s * 2 ** (attempt - 1))
    raise AssertionError("unreachable")
