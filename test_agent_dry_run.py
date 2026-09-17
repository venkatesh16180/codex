# test_agent_dry_run.py -- Phase 15
#
# Runs against the REAL database (conn fixture, conftest.py) -- inserts a
# throwaway source_documents/document_chunks pair, deletes both in a finally
# block, following test_isolation.py's existing insert-then-cleanup
# discipline rather than an isolated fixture DB. Only the Ollama call itself
# is mocked (via agent.chat_with_retry), since no real model call is needed
# to prove the dry_run/result_sink contract.
from unittest.mock import MagicMock
import agent


def test_dry_run_writes_nothing_to_pending_actions(conn):
    conn.execute(
        '''INSERT INTO source_documents (file_path, file_hash, title, file_type)
           VALUES ('_test.txt', '_test_hash_phase15_dry_run', 'Phase 15 Test Doc', 'txt')'''
    )
    document_id = conn.execute(
        'SELECT document_id FROM source_documents WHERE file_hash=?',
        ('_test_hash_phase15_dry_run',)
    ).fetchone()['document_id']
    conn.execute(
        'INSERT INTO document_chunks (document_id, chunk_index, chunk_text, embedding) VALUES (?, 0, ?, ?)',
        (document_id, 'irrelevant test content', b'')
    )
    conn.commit()

    fake_call = MagicMock()
    fake_call.function.name = 'flag_for_manual_review'
    fake_call.function.arguments = {'rationale': 'phase15 test'}
    fake_response = MagicMock()
    fake_response.message.tool_calls = [fake_call]

    real_chat_with_retry = agent.chat_with_retry
    agent.chat_with_retry = lambda client, **kw: fake_response
    try:
        before = conn.execute('SELECT COUNT(*) c FROM pending_actions').fetchone()['c']
        result = agent.triage_document(conn, embed_model=MagicMock(), document_id=document_id, dry_run=True)
        after = conn.execute('SELECT COUNT(*) c FROM pending_actions').fetchone()['c']
    finally:
        agent.chat_with_retry = real_chat_with_retry
        conn.execute('DELETE FROM document_chunks WHERE document_id=?', (document_id,))
        conn.execute('DELETE FROM source_documents WHERE document_id=?', (document_id,))
        conn.commit()

    assert before == after, 'dry_run wrote to pending_actions -- Phase 12 guard broken'
    assert result is not None and result['action_type'] == 'manual_review'