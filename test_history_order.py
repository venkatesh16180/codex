# test_history_order.py -- Phase 20
#
# chat_messages.created_at has one-second resolution (datetime('now')), so a question and
# its answer saved back to back can tie. Ordering on created_at alone left tie order
# undefined, and get_recent_history() -- which orders DESC then reverses -- could hand the
# model an exchange with the answer before the question. message_id breaks the tie.
from history import create_session, get_recent_history, load_session_messages, save_message


def _conversation(db):
    db.execute("INSERT INTO specialists (slug, display_name, scope_description) VALUES ('s', 'S', 'x')")
    session_id = create_session(db, 1, 'q1')
    for role, text in [('user', 'q1'), ('assistant', 'a1'), ('user', 'q2'), ('assistant', 'a2')]:
        save_message(db, session_id, role, text)
    db.execute("UPDATE chat_messages SET created_at = '2026-01-01 00:00:00'")   # force the tie
    db.commit()
    return session_id


def test_loaded_messages_keep_insertion_order_when_timestamps_tie(fresh_db):
    session_id = _conversation(fresh_db)
    assert [m['content'] for m in load_session_messages(fresh_db, session_id)] == ['q1', 'a1', 'q2', 'a2']


def test_recent_history_is_oldest_first_when_timestamps_tie(fresh_db):
    session_id = _conversation(fresh_db)
    history = get_recent_history(fresh_db, session_id, turns=1)
    assert [(m['role'], m['content']) for m in history] == [('user', 'q2'), ('assistant', 'a2')]
