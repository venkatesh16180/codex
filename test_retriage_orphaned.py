# test_retriage_orphaned.py -- Phase 20
#
# add_source.py skips an already-ingested file forever (hash dedup), so a document whose
# triage failed after ingestion needs its own recovery path. The recovery's whole
# correctness is in one query: not committed, and no pending_actions row at all.
from retriage_orphaned import find_orphaned


def _document(db, file_hash, title, status='untriaged'):
    cur = db.execute(
        "INSERT INTO source_documents (file_path, file_hash, title, file_type, triage_status) "
        "VALUES ('_p', ?, ?, 'txt', ?)", (file_hash, title, status))
    return cur.lastrowid


def _stage(db, document_id, status):
    db.execute("INSERT INTO pending_actions (action_type, document_id, agent_rationale, status) "
               "VALUES ('manual_review', ?, 'x', ?)", (document_id, status))


def test_only_untriaged_documents_with_no_proposal_are_orphaned(fresh_db):
    _document(fresh_db, 'h1', 'Orphan')
    staged = _document(fresh_db, 'h2', 'Staged')
    _document(fresh_db, 'h3', 'Committed', status='committed')
    rejected = _document(fresh_db, 'h4', 'Rejected')
    _stage(fresh_db, staged, 'pending')
    _stage(fresh_db, rejected, 'rejected')     # triaged, then rejected: has a row, so not an orphan
    fresh_db.commit()
    assert [r['title'] for r in find_orphaned(fresh_db)] == ['Orphan']


def test_nothing_is_orphaned_in_an_empty_library(fresh_db):
    assert find_orphaned(fresh_db) == []
