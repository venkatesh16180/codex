# ollama_retry.py
"""
Shared retry wrapper for Ollama calls (Phase 14).

Retries genuine connection failures (server not up yet, transient network blip).
Never retries a real read/write/pool timeout -- LLM_TRIAGE_TIMEOUT_SEC is already
a 3hr ceiling with margin above the real 124.6-min max; retrying that would double
an already enormous wait instead of surfacing a real failure to the caller.

Connection-error detection note (confirmed by a real dev_checks test run, not
assumed from reading docs): ollama-python's own _request_raw() catches
httpx.ConnectError internally and re-raises it as the BUILTIN ConnectionError
with a fixed message -- the raw httpx exception never reaches this wrapper.
httpx.ConnectTimeout is NOT wrapped this way and would arrive unwrapped if it
ever happened, so it's kept here too, defensively.
"""
import time
import httpx
import ollama
from logging_setup import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2  # doubles each attempt: 2s, 4s, 8s

# The real-world connect failure case, per ollama-python's source: it wraps
# httpx.ConnectError into Python's builtin ConnectionError before it reaches
# any caller. httpx.ConnectTimeout is included defensively -- it is NOT
# wrapped by ollama-python and would arrive as-is.
_CONNECTION_ERRORS = (ConnectionError, httpx.ConnectError, httpx.ConnectTimeout)


def chat_with_retry(client: ollama.Client, **kwargs):
    """Call client.chat(**kwargs), retrying connection errors only.

    Clause order matters: httpx.ConnectTimeout is a SUBCLASS of
    httpx.TimeoutException, and Python matches the first except clause that
    fits. The connection-error clause must come first, or every
    ConnectTimeout would fall into the "never retry" branch below.

    A genuine read/write/pool timeout (httpx.TimeoutException, not a
    connect-phase one) propagates immediately, uncaught -- that's the
    caller's real answer, not something to paper over.
    """
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.chat(**kwargs)
        except _CONNECTION_ERRORS as exc:
            last_exc = exc
            wait = RETRY_BACKOFF_SEC * (2 ** (attempt - 1))
            logger.warning(
                'ollama connection error (attempt %d/%d): %s -- retrying in %ds',
                attempt, MAX_RETRIES, exc, wait
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)
        except httpx.TimeoutException:
            raise  # a real read/write/pool timeout -- never retry, see docstring
    raise last_exc