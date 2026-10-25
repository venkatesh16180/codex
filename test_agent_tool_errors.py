# test_agent_tool_errors.py -- Phase 20
#
# A small tool-calling model can emit wrong argument names. Before Phase 20,
# agent.py called fn(**arguments) unguarded, so a TypeError escaped triage_document
# and left the document ingested but never triaged. Only the Ollama call is mocked;
# the tools, the loop and the database (an isolated in-memory one) are real.
from unittest.mock import MagicMock

import agent


def _response(tool_name, arguments):
    call = MagicMock()
    call.function.name = tool_name
    call.function.arguments = arguments
    response = MagicMock()
    response.message.tool_calls = [call]
    return response


def test_bad_tool_arguments_are_retried_not_fatal(fresh_db, monkeypatch):
    fresh_db.execute(
        "INSERT INTO source_documents (file_path, file_hash, title, file_type) "
        "VALUES ('_t.txt', '_h', 'Tool Error Test Doc', 'txt')")
    fresh_db.execute(
        "INSERT INTO document_chunks (document_id, chunk_index, chunk_text, embedding) "
        "VALUES (1, 0, 'irrelevant test content', ?)", (b'',))
    fresh_db.commit()

    responses = iter([
        _response('propose_categorization', {'slug': 'x', 'why': 'wrong argument names'}),
        _response('flag_for_manual_review', {'rationale': 'recovered after the bad call'}),
    ])
    monkeypatch.setattr(agent, 'chat_with_retry', lambda client, **kw: next(responses))

    agent.triage_document(fresh_db, MagicMock(), 1)   # must not raise

    rows = fresh_db.execute('SELECT action_type, source_backend FROM pending_actions').fetchall()
    assert len(rows) == 1
    assert rows[0]['action_type'] == 'manual_review'
    assert rows[0]['source_backend'] == 'llm'
