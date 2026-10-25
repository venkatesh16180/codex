# test_schema_builds.py -- Phase 20
#
# schema.sql is what CI and every fresh clone bootstrap from, but no local test
# ever read it (conftest.py's `conn` points at the live database). A stray
# trailing comma in pending_actions broke CI and would have broken a fresh
# clone, and nothing local could have caught it. This is that test.
EXPECTED_TABLES = {
    'specialists', 'source_documents', 'document_chunks', 'specialist_chunks',
    'pending_actions', 'chat_sessions', 'chat_messages', 'jobs',
}


def test_schema_sql_builds_every_expected_table(fresh_db):
    tables = {r['name'] for r in fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= tables


def test_pending_actions_accepts_source_backend(fresh_db):
    fresh_db.execute(
        "INSERT INTO pending_actions (action_type, agent_rationale, source_backend) "
        "VALUES ('manual_review', 'schema test', 'llm')")
    row = fresh_db.execute('SELECT source_backend FROM pending_actions').fetchone()
    assert row['source_backend'] == 'llm'
