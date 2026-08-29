# migrate_add_chat_history.py -- one-time: adds chat_sessions/chat_messages
# to an already-running librarian.db without touching existing tables/data
from db import get_connection

MIGRATION_SQL = '''
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    specialist_id INTEGER NOT NULL REFERENCES specialists(specialist_id),
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(session_id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    used_web BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
'''

if __name__ == '__main__':
    conn = get_connection()
    conn.executescript(MIGRATION_SQL)
    conn.commit()
    print('Migration complete: chat_sessions and chat_messages tables ready.')

    # Confirm against real state, not just assume the executescript succeeded silently
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print('Current tables:', [t['name'] for t in tables])
    conn.close()