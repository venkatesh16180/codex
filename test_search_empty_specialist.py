# test_search_empty_specialist.py -- Phase 15
#
# Replaces dev_checks/test_empty_specialist.py, whose hardcoded assumption
# (philosopher_mentor has no committed chunks) went stale the moment real
# documents were triaged into that specialist -- confirmed against the real
# DB: philosopher_mentor now has 904 committed chunks across 3 real source
# documents. Any specific specialist can gain content at any time, so this
# version creates and deletes its own guaranteed-empty specialist instead of
# depending on a named one staying empty by luck.
#
# embed_model.encode() is never actually called for a genuinely empty
# specialist -- search_specialist returns [] before reaching that line -- so
# a MagicMock() is safe here without needing sentence_transformers at all.
from unittest.mock import MagicMock
from search import search_specialist


def test_search_specialist_returns_empty_list_for_specialist_with_no_chunks(conn):
    conn.execute(
        '''INSERT INTO specialists (slug, display_name, scope_description, status)
           VALUES ('_test_empty_phase15', 'Test Empty', 'throwaway for phase15 test', 'active')'''
    )
    specialist_id = conn.execute(
        "SELECT specialist_id FROM specialists WHERE slug='_test_empty_phase15'"
    ).fetchone()['specialist_id']
    conn.commit()

    try:
        result = search_specialist(conn, MagicMock(), specialist_id, 'test query', top_k=5)
    finally:
        conn.execute('DELETE FROM specialists WHERE specialist_id=?', (specialist_id,))
        conn.commit()

    assert result == []