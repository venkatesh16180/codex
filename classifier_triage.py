# classifier_triage.py
import joblib
from logging_setup import get_logger
from content_preview import find_real_content_start

from agent import FRONT_MATTER_SCAN_LIMIT  # reuse the same constant, don't duplicate it

_model_cache = None

def _load_model():
    global _model_cache
    if _model_cache is None:
        _model_cache = joblib.load(MODEL_PATH)
    return _model_cache

logger = get_logger(__name__)
MODEL_PATH = 'data/triage_classifier.joblib'
CONFIDENCE_THRESHOLD = 0.14  # from dev_checks/calibrate_confidence_threshold.py's LOOCV run:
                              # 0 errors at or above this confidence, 6/6 errors below it.
                              # Based on only 22 documents -- recalibrate as the corpus grows.

def classifier_triage(conn, document_id: int) -> dict:
    bundle = _load_model()
    vectorizer, clf = bundle['vectorizer'], bundle['classifier']

    all_chunks = conn.execute(
        'SELECT chunk_text FROM document_chunks WHERE document_id=? ORDER BY chunk_index',
        (document_id,)
    ).fetchall()
    start_idx = find_real_content_start(all_chunks[:FRONT_MATTER_SCAN_LIMIT])
    text = ' '.join(c['chunk_text'] for c in all_chunks[start_idx:])[:16000]  # match Phase 11's tuned cap

    X = vectorizer.transform([text])
    proba = clf.predict_proba(X)[0]
    best_idx = proba.argmax()
    specialist_slug, confidence = str(clf.classes_[best_idx]), proba[best_idx]

    if confidence < CONFIDENCE_THRESHOLD:
        decision = {'action_type': 'manual_review',
                    'rationale': f'Classifier confidence {confidence:.2f} below threshold '
                                 f'{CONFIDENCE_THRESHOLD} -- may be a genuinely novel topic '
                                 f'the classifier cannot propose a new specialist for.'}
    else:
        decision = {'action_type': 'categorize_document', 'specialist_slug': specialist_slug,
                    'rationale': f'Classifier prediction, confidence={confidence:.2f}.'}

    logger.info('classifier_triage doc=%s pred=%s confidence=%.2f', document_id, specialist_slug, confidence)
    return decision

def stage_classifier_decision(conn, document_id: int, decision: dict) -> None:
    """Write a classifier_triage() decision to pending_actions. Kept separate from
    classifier_triage() itself so review_pending.py's cross-check display (13.5) can
    call classifier_triage() for information only, without ever staging anything."""
    if decision['action_type'] == 'categorize_document':
        row = conn.execute(
            "SELECT specialist_id FROM specialists WHERE slug=? AND status='active'",
            (decision['specialist_slug'],)
        ).fetchone()
        if row is None:
            decision = {'action_type': 'manual_review',
                        'rationale': f"Classifier predicted '{decision['specialist_slug']}', "
                                     f"but that specialist is no longer active."}
        else:
            conn.execute(
                '''INSERT INTO pending_actions
                   (action_type, document_id, target_specialist_id, agent_rationale)
                   VALUES ('categorize_document', ?, ?, ?)''',
                (document_id, row['specialist_id'], decision['rationale'])
            )
            conn.commit()
            return
    # falls through here for manual_review, whether original or the fallback above
    conn.execute(
        "INSERT INTO pending_actions (action_type, document_id, agent_rationale) VALUES ('manual_review', ?, ?)",
        (document_id, decision['rationale'])
    )
    conn.commit()