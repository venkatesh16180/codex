# migrate_add_jobs.py -- one-time: adds a `jobs` table to an already-running
# librarian.db without touching existing tables/data
from db import get_connection

MIGRATION_SQL = '''
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    document_id INTEGER REFERENCES source_documents(document_id),
    backend TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing',
    started_at REAL NOT NULL,   -- epoch float (time.time()), NOT datetime('now') --
                                -- matches check_status()'s existing elapsed_sec math,
                                -- deliberately inconsistent with this schema's other
                                -- TEXT/datetime('now') columns for that reason
    finished_at REAL,
    error TEXT
);
'''

if __name__ == '__main__':
    conn = get_connection()
    conn.executescript(MIGRATION_SQL)
    conn.commit()
    print('Migration complete: jobs table ready.')

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print('Current tables:', [t['name'] for t in tables])
    conn.close()