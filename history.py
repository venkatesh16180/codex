# history.py
def create_session(conn, specialist_id: int, first_question: str) -> int:
    title = first_question[:50] + ('...' if len(first_question) > 50 else '')
    cur = conn.execute(
        'INSERT INTO chat_sessions (specialist_id, title) VALUES (?, ?)',
        (specialist_id, title)
    )
    conn.commit()
    return cur.lastrowid

def save_message(conn, session_id: int, role: str, content: str, used_web: bool = False):
    conn.execute(
        'INSERT INTO chat_messages (session_id, role, content, used_web) VALUES (?, ?, ?, ?)',
        (session_id, role, content, used_web)
    )
    conn.execute(
        "UPDATE chat_sessions SET updated_at=datetime('now') WHERE session_id=?",
        (session_id,)
    )
    conn.commit()

def list_sessions(conn, specialist_id: int):
    return conn.execute(
        '''SELECT session_id, title, created_at, updated_at
           FROM chat_sessions WHERE specialist_id=?
           ORDER BY updated_at DESC''',
        (specialist_id,)
    ).fetchall()

def load_session_messages(conn, session_id: int):
    return conn.execute(
        '''SELECT role, content, used_web, created_at
           FROM chat_messages WHERE session_id=?
           ORDER BY created_at ASC''',
        (session_id,)
    ).fetchall()
    
def rename_session(conn, session_id: int, new_title: str):
    conn.execute(
        "UPDATE chat_sessions SET title=?, updated_at=datetime('now') WHERE session_id=?",
        (new_title, session_id)
    )
    conn.commit()
    
def export_session_as_markdown(conn, session_id: int) -> str:
    session = conn.execute(
        'SELECT title FROM chat_sessions WHERE session_id=?', (session_id,)
    ).fetchone()
    messages = load_session_messages(conn, session_id)

    lines = [f"# {session['title'] or f'Session {session_id}'}", '']
    for m in messages:
        speaker = 'You' if m['role'] == 'user' else 'Assistant'
        lines.append(f"**{speaker}:** {m['content']}")
        lines.append('')
    return '\n'.join(lines)

def delete_session(conn, session_id: int):
    conn.execute('DELETE FROM chat_messages WHERE session_id=?', (session_id,))
    conn.execute('DELETE FROM chat_sessions WHERE session_id=?', (session_id,))
    conn.commit()
    
def get_recent_history(conn, session_id: int, turns: int = 3):
    """Most recent `turns` question/answer pairs for a session, oldest first,
    formatted as chat messages ready to feed into another LLM call."""
    if session_id is None:
        return []
    rows = conn.execute(
        '''SELECT role, content FROM chat_messages
           WHERE session_id=? ORDER BY created_at DESC LIMIT ?''',
        (session_id, turns * 2)
    ).fetchall()
    return [{'role': r['role'], 'content': r['content']} for r in reversed(rows)]