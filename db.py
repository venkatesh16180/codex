import sqlite3
# db.py -- was: DB_PATH = "data/librarian.db"
from config import DB_PATH

# Phase 16 -- was: def get_connection(): (no parameter)
# check_same_thread=True is sqlite3's own real default, so every existing
# caller (agent.py, ingest.py, review_pending.py, test files, etc.) is
# completely unaffected. Only streamlit_app.py passes False, because it
# needs to cache and reuse ONE connection object across Streamlit's reruns
# via @st.cache_resource, which can hand that object back on a different
# internal thread than the one that created it.
def get_connection(check_same_thread: bool = True):
    conn = sqlite3.connect(DB_PATH, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row   # lets later code do row['column_name'] instead of row[0]
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn