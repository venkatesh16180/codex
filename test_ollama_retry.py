# test_ollama_retry.py -- Phase 15
#
# Pure mocks, no DB, no real Ollama server -- locks in the two real bugs
# found and fixed in Phase 14 (the builtin-ConnectionError wrapping issue,
# the ConnectTimeout/TimeoutException ordering issue), verified interactively
# against the real ollama_retry.py before being written here.
import httpx
import pytest
from unittest.mock import MagicMock
from ollama_retry import chat_with_retry, MAX_RETRIES


def test_connection_error_retries_then_raises():
    client = MagicMock()
    client.chat.side_effect = ConnectionError('Failed to connect to Ollama.')
    with pytest.raises(ConnectionError):
        chat_with_retry(client, model='x', messages=[])
    assert client.chat.call_count == MAX_RETRIES


def test_read_timeout_never_retries():
    client = MagicMock()
    client.chat.side_effect = httpx.ReadTimeout('timed out')
    with pytest.raises(httpx.ReadTimeout):
        chat_with_retry(client, model='x', messages=[])
    assert client.chat.call_count == 1


def test_connect_timeout_is_retried_not_swallowed_by_timeout_clause():
    """Regression test for the exception-ordering bug caught in Phase 14 --
    httpx.ConnectTimeout is a TimeoutException subclass and must still be
    retried, not fall into the generic never-retry branch."""
    client = MagicMock()
    client.chat.side_effect = httpx.ConnectTimeout('timed out connecting')
    with pytest.raises(httpx.ConnectTimeout):
        chat_with_retry(client, model='x', messages=[])
    assert client.chat.call_count == MAX_RETRIES