# migrate_add_source_backend.py -- one-time: adds pending_actions.source_backend
# to an already-running librarian.db without touching existing data
from db import get_connection

MIGRATION_SQL = '''
ALTER TABLE pending_actions ADD COLUMN source_backend TEXT;
'''

if __name__ == '__main__':
    conn = get_connection()
    conn.executescript(MIGRATION_SQL)
    conn.commit()
    print('Migration complete: pending_actions.source_backend added.')

    cols = conn.execute("PRAGMA table_info(pending_actions)").fetchall()
    print('Current columns:', [c['name'] for c in cols])
    conn.close()