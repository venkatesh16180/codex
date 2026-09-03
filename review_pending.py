# review_pending.py
from logging_setup import get_logger

def review_pending(conn):
    pending = conn.execute(
        """SELECT pa.*, sd.title AS document_title, sp.display_name AS target_specialist_name
           FROM pending_actions pa
           JOIN source_documents sd ON sd.document_id = pa.document_id
           LEFT JOIN specialists sp ON sp.specialist_id = pa.target_specialist_id
           WHERE pa.status='pending' ORDER BY pa.created_at"""
    ).fetchall()

    logger = get_logger(__name__)
    logger.info('pending_actions_reviewed count=%d', len(pending))

    if not pending:
        return

    for action in pending:
        print_summary(action)  # title, target specialist or proposed new one, agent_rationale
        choice = input('[a]pprove / [r]eject / [s]kip: ').strip().lower()

        if choice == 'a':
            persona_style = None
            if action['action_type'] == 'propose_specialist':
                draft = action['proposed_persona_style']
                if draft:
                    prompt = f"Persona style [Enter to accept: '{draft}', or type to override, or 'none' to clear]: "
                else:
                    prompt = 'Persona style for this new specialist (optional, Enter to skip): '
                typed = input(prompt).strip()
                if typed.lower() == 'none':
                    persona_style = None
                elif typed:
                    persona_style = typed
                else:
                    persona_style = draft  # accept the agent's draft as-is, or stay None if it had none

            committed = commit_action(conn, action, persona_style=persona_style)
            if not committed:
                # commit_action already printed why. Leave status='pending' so this
                # doesn't get silently lost -- reviewer can resolve the slug collision
                # (reject one of the proposals, or edit the slug directly) and rerun.
                print('Left pending -- resolve the conflict above and run review_pending.py again.')
                continue

        elif choice == 'r':
            note = input('Reason (optional): ')
            conn.execute(
                "UPDATE pending_actions SET status='rejected', resolved_at=datetime('now'), "
                "resolver_note=? WHERE action_id=?",
                (note, action['action_id'])
            )
            conn.commit()
        # 's' or anything else: leave it pending, move on

def commit_action(conn, action, persona_style=None):
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
        # Guard against a slug collision -- two documents can genuinely and honestly
        # propose the same new specialist independently. Without this check, approving
        # the second one mid-session raises an unhandled sqlite3.IntegrityError on the
        # UNIQUE constraint and kills the whole review loop.
        existing = conn.execute(
            'SELECT specialist_id, status FROM specialists WHERE slug=?',
            (action['proposed_specialist_slug'],)
        ).fetchone()
        if existing is not None:
            print(f"Cannot approve: a specialist with slug "
                  f"'{action['proposed_specialist_slug']}' already exists "
                  f"(specialist_id={existing['specialist_id']}, status={existing['status']}). "
                  f"If this document should join that specialist instead, reject this "
                  f"proposal and stage it as categorize_document instead.")
            return False

        cur = conn.execute(
            '''INSERT INTO specialists (slug, display_name, scope_description, persona_style, status, approved_at)
               VALUES (?, ?, ?, ?, 'active', datetime('now'))''',
            (action['proposed_specialist_slug'],
             action['proposed_specialist_slug'].replace('_', ' ').title(),
             action['proposed_specialist_description'],
             persona_style)
        )
        new_specialist_id = cur.lastrowid

        # The document that justified proposing this specialist in the first place
        # has to actually land in it -- otherwise approval creates an empty specialist
        # with nothing retrievable behind it. Same commit logic as categorize_document,
        # just against the specialist that was just created rather than an existing one.
        chunk_ids = conn.execute(
            'SELECT chunk_id FROM document_chunks WHERE document_id=?',
            (action['document_id'],)
        ).fetchall()
        for row in chunk_ids:
            conn.execute(
                'INSERT OR IGNORE INTO specialist_chunks (specialist_id, chunk_id) VALUES (?, ?)',
                (new_specialist_id, row['chunk_id'])
            )
        conn.execute(
            "UPDATE source_documents SET triage_status='committed' WHERE document_id=?",
            (action['document_id'],)
        )
    # manual_review: nothing to commit -- you handle it outside the automated flow

    conn.execute(
        "UPDATE pending_actions SET status='approved', resolved_at=datetime('now') WHERE action_id=?",
        (action['action_id'],)
    )
    conn.commit()
    return True

def print_summary(action):
    print(f"\n--- pending_action #{action['action_id']} ---")
    print(f"Document: {action['document_title']}")
    print(f"Type: {action['action_type']}")

    if action['action_type'] == 'categorize_document':
        print(f"Proposed specialist: {action['target_specialist_name']}")
    elif action['action_type'] == 'propose_specialist':
        print(f"Proposed new specialist: {action['proposed_specialist_slug']}")
        print(f"Description: {action['proposed_specialist_description']}")
        if action['proposed_persona_style']:
            print(f"Agent-drafted persona: {action['proposed_persona_style']}")
    elif action['action_type'] == 'manual_review':
        print("No target specialist -- flagged for manual review")

    print(f"Agent rationale: {action['agent_rationale']}")

if __name__ == '__main__':
    from db import get_connection
    conn = get_connection()
    review_pending(conn)
    conn.close()