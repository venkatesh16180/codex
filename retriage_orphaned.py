# retriage_orphaned.py -- triage documents that were ingested but never triaged.
#
# add_source.py skips a file it has already ingested (hash dedup), so if triage failed -- or
# the process died -- after ingestion, rerunning add_source.py will never triage that
# document. This finds those documents and triages them.
#
# "Orphaned" means: not committed, and no pending_actions row at all. That row is only ever
# created by a successful triage, so its absence is the reliable signal; a document whose
# proposal was rejected still has its row and is correctly NOT treated as orphaned.
#
#   python retriage_orphaned.py                       # triage with the Librarian (slow)
#   python retriage_orphaned.py --backend classifier  # ...or with the classifier
#   python retriage_orphaned.py --list                # just show what would be triaged
import argparse
import os
import sys


def find_orphaned(conn):
    return conn.execute(
        '''SELECT sd.document_id, sd.title FROM source_documents sd
           WHERE sd.triage_status != 'committed'
           AND NOT EXISTS (
               SELECT 1 FROM pending_actions pa WHERE pa.document_id = sd.document_id
           )
           ORDER BY sd.document_id'''
    ).fetchall()


def main(backend='llm', list_only=False):
    os.environ['HF_HUB_OFFLINE'] = '1'
    from db import get_connection

    conn = get_connection()
    orphaned = find_orphaned(conn)
    print(f"Found {len(orphaned)} ingested-but-untriaged document(s): {[o['title'] for o in orphaned]}")
    if list_only or not orphaned:
        conn.close()
        return

    if backend == 'classifier':
        from classifier_triage import classifier_triage, stage_classifier_decision
    else:
        from sentence_transformers import SentenceTransformer
        from agent import triage_document
        embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    failed = []
    done = 0
    for doc in orphaned:
        print(f"\n--- Triaging: {doc['title']} ---")
        try:
            if backend == 'classifier':
                stage_classifier_decision(conn, doc['document_id'],
                                          classifier_triage(conn, doc['document_id']))
            else:
                triage_document(conn, embed_model, doc['document_id'])
            done += 1
        except Exception as e:
            failed.append((doc['document_id'], doc['title'], e))
            print(f"  FAILED: {type(e).__name__}: {e}")
            if isinstance(e, ConnectionError):
                print('Ollama is unreachable (retries exhausted) -- stopping.')
                break
    conn.close()

    print(f"\n{done} of {len(orphaned)} triaged.")
    if done < len(orphaned):
        print('Still untriaged (run this again once the cause is fixed):')
        for document_id, title, e in failed:
            print(f'  document_id={document_id}  {title}  ({type(e).__name__})')
        if len(failed) < len(orphaned) - done:
            print(f'  ...and {len(orphaned) - done - len(failed)} not attempted')
        sys.exit(1)
    print('Run `python review_pending.py` to approve or reject before anything goes live.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Triage documents that were ingested but never triaged.')
    parser.add_argument('--backend', choices=['llm', 'classifier'], default='llm')
    parser.add_argument('--list', action='store_true', dest='list_only', help='only list orphaned documents')
    args = parser.parse_args()
    main(backend=args.backend, list_only=args.list_only)
