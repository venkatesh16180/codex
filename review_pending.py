# review_pending.py

def review_pending(conn):
    pending = conn.execute(
        """SELECT pa.*, sd.title AS document_title, sp.display_name AS target_specialist_name
           FROM pending_actions pa
           JOIN source_documents sd ON sd.document_id = pa.document_id
           LEFT JOIN specialists sp ON sp.specialist_id = pa.target_specialist_id
           WHERE pa.status='pending' ORDER BY pa.created_at"""
    ).fetchall()

    if not pending:
        print('Nothing to review.')
        return

    for action in pending:
        print_summary(action)  # title, target specialist or proposed new one, agent_rationale
        choice = input('[a]pprove / [r]eject / [s]kip: ').strip().lower()

        if choice == 'a':
            commit_action(conn, action)
        elif choice == 'r':
            note = input('Reason (optional): ')
            conn.execute(
                "UPDATE pending_actions SET status='rejected', resolved_at=datetime('now'), "
                "resolver_note=? WHERE action_id=?",
                (note, action['action_id'])
            )
            conn.commit()
        # 's' or anything else: leave it pending, move on
        
def commit_action(conn, action):
    if action['action_type'] == 'categorize_document':
        chunk_ids = conn.execute(
            'SELECT chunk_id FROM document_chunks WHERE document_id=?',
            (action['document_id'],)
        ).fetchall()
        for row in chunk_ids:
            conn.execute(
                'INSERT OR IGNORE INTO specialist_chunks (specialist_id, chunk_id) VALUES (?, ?)',
                (action['target_specialist_id'], row['chunk_id'])
            )
        conn.execute(
            "UPDATE source_documents SET triage_status='committed' WHERE document_id=?",
            (action['document_id'],)
        )

    elif action['action_type'] == 'propose_specialist':
        conn.execute(
            '''INSERT INTO specialists (slug, display_name, scope_description, status, approved_at)
               VALUES (?, ?, ?, 'active', datetime('now'))''',
            (action['proposed_specialist_slug'],
             action['proposed_specialist_slug'].replace('_', ' ').title(),
             action['proposed_specialist_description'])
        )
    # manual_review: nothing to commit -- you handle it outside the automated flow

    conn.execute(
        "UPDATE pending_actions SET status='approved', resolved_at=datetime('now') WHERE action_id=?",
        (action['action_id'],)
    )
    conn.commit()
    
def print_summary(action):
    print(f"\n--- pending_action #{action['action_id']} ---")
    print(f"Document: {action['document_title']}")
    print(f"Type: {action['action_type']}")

    if action['action_type'] == 'categorize_document':
        print(f"Proposed specialist: {action['target_specialist_name']}")
    elif action['action_type'] == 'propose_specialist':
        print(f"Proposed new specialist: {action['proposed_specialist_slug']}")
        print(f"Description: {action['proposed_specialist_description']}")
    elif action['action_type'] == 'manual_review':
        print("No target specialist -- flagged for manual review")

    print(f"Agent rationale: {action['agent_rationale']}")
    
if __name__ == '__main__':
    from db import get_connection
    conn = get_connection()
    review_pending(conn)
    conn.close()