# test_isolation.py
import sys, os
os.environ['HF_HUB_OFFLINE'] = '1'
from db import get_connection
from sentence_transformers import SentenceTransformer
from search import search_specialist
from agent import make_tools


def get_specialist_id(conn, slug):
    row = conn.execute('SELECT specialist_id FROM specialists WHERE slug=?', (slug,)).fetchone()
    if row is None:
        raise RuntimeError(f"No specialist with slug '{slug}' -- has your seed data changed?")
    return row['specialist_id']


def test_cross_specialist_isolation(conn, embed_model):
    phil_id = get_specialist_id(conn, 'philosopher_mentor')
    fit_id = get_specialist_id(conn, 'fitness_mentor')

    phil_results = search_specialist(conn, embed_model, phil_id, 'progressive overload deadlift form')
    fit_results = search_specialist(conn, embed_model, fit_id, 'the Stoic dichotomy of control')

    assert all(r['score'] < 0.3 for r in phil_results), 'fitness content leaking into philosopher search'
    assert all(r['score'] < 0.3 for r in fit_results), 'philosophy content leaking into fitness search'


def test_empty_specialist_no_crash(conn, embed_model):
    # Throwaway specialist created and torn down inside the test itself, rather than
    # pointing at one of the real 9 -- keeps this test valid regardless of what's
    # actually committed in the library when it runs (especially now that "just point
    # it at whichever real specialist is empty" is no longer a safe assumption at all,
    # now that the backfill fixed the ones that used to be).
    conn.execute(
        '''INSERT INTO specialists (slug, display_name, scope_description, status)
           VALUES ('_test_empty_specialist_tmp', 'Test Empty Specialist', 'throwaway for test_isolation.py', 'active')'''
    )
    conn.commit()
    tmp_id = get_specialist_id(conn, '_test_empty_specialist_tmp')

    try:
        result = search_specialist(conn, embed_model, tmp_id, 'anything')
        assert result == [], 'expected empty list for a specialist with no committed chunks'
    finally:
        conn.execute('DELETE FROM specialists WHERE specialist_id=?', (tmp_id,))
        conn.commit()


def test_malformed_specialist_slug_recovers(conn, embed_model):
    # Any real, already-committed document works here -- propose_categorization
    # rejects the bad slug before it ever inserts anything, so this can't leave a
    # stray pending_actions row behind regardless of which document_id gets used.
    document_id = conn.execute(
        "SELECT document_id FROM source_documents WHERE triage_status='committed' LIMIT 1"
    ).fetchone()['document_id']

    # Baseline, not zero -- a real, already-triaged document has its own approved
    # pending_actions row (or several) from actually getting committed in the first
    # place. What this test needs to prove is that the malformed call adds nothing
    # new, not that the document has no history at all.
    before_count = conn.execute(
        "SELECT COUNT(*) c FROM pending_actions WHERE document_id=?", (document_id,)
    ).fetchone()['c']

    tools = make_tools(conn, document_id, embed_model)
    propose = {t.__name__: t for t in tools}['propose_categorization']
    msg = propose(specialist_slug='does_not_exist', rationale='test')

    assert 'ERROR: No active specialist' in msg

    after_count = conn.execute(
        "SELECT COUNT(*) c FROM pending_actions WHERE document_id=?", (document_id,)
    ).fetchone()['c']
    assert after_count == before_count, 'a failed proposal should not have staged anything new'


TESTS = [test_cross_specialist_isolation, test_empty_specialist_no_crash, test_malformed_specialist_slug_recovers]

if __name__ == '__main__':
    conn = get_connection()
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    failures = 0
    for test in TESTS:
        try:
            test(conn, embed_model)
            print(f'PASS: {test.__name__}')
        except AssertionError as e:
            failures += 1
            print(f'FAIL: {test.__name__} -- {e}')
        except Exception as e:
            failures += 1
            print(f'ERROR: {test.__name__} -- {type(e).__name__}: {e}')

    conn.close()
    print(f'\n{len(TESTS) - failures}/{len(TESTS)} passed.')
    sys.exit(1 if failures else 0)