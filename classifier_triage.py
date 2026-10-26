# classifier_triage.py
import joblib
import sklearn
from logging_setup import get_logger
from content_preview import build_classifier_text, CLASSIFIER_MAX_CHARS

logger = get_logger(__name__)
MODEL_PATH = 'data/triage_classifier.joblib'
CONFIDENCE_THRESHOLD = 0.14  # LOOCV on 27 docs, shared text prep (Phase 20), 4-decimal confidences:
                              # highest error 0.1380 (doc 17), lowest accepted-correct 0.1415 (doc 40); 0.14 sits between.
                              # At 0.14: 13/13 accepted correct, 8/8 errors abstained, 6/19 correct abstained.
                              # Kept deliberately, see BUILD-JOURNAL. Recalibrate as the corpus grows.

_model_cache = None

def _load_model():
    global _model_cache
    if _model_cache is None:
        bundle = joblib.load(MODEL_PATH)
        meta = bundle.get('meta')
        if meta is None:
            logger.warning('classifier_model_no_metadata path=%s -- trained before Phase 20; '
                           'retrain with train_final_classifier.py', MODEL_PATH)
        else:
            logger.info('classifier_model_loaded n_docs=%s n_classes=%s trained_at=%s',
                        meta['n_docs'], len(meta['classes']), meta['trained_at'])
            if meta['sklearn_version'] != sklearn.__version__:
                logger.warning('classifier_model_sklearn_mismatch trained=%s running=%s -- '
                               'confidences may differ from training; retrain',
                               meta['sklearn_version'], sklearn.__version__)
            if meta['max_chars'] != CLASSIFIER_MAX_CHARS:
                logger.warning('classifier_model_max_chars_mismatch trained=%s current=%s -- '
                               're-export and retrain', meta['max_chars'], CLASSIFIER_MAX_CHARS)
        _model_cache = bundle
    return _model_cache

def classifier_triage(conn, document_id: int) -> dict:
    bundle = _load_model()
    vectorizer, clf = bundle['vectorizer'], bundle['classifier']

    all_chunks = conn.execute(
        'SELECT chunk_text FROM document_chunks WHERE document_id=? ORDER BY chunk_index',
        (document_id,)
    ).fetchall()
    text, _ = build_classifier_text(all_chunks)   # the same function the export uses (Phase 20)

    X = vectorizer.transform([text])
    proba = clf.predict_proba(X)[0]
    best_idx = proba.argmax()
    specialist_slug, confidence = str(clf.classes_[best_idx]), float(proba[best_idx])

    # Four decimals: at two, a confidence of 0.1399 and one of 0.1401 both print as 0.14,
    # which hid whether documents 17 and 40 sat above or below the threshold.
    if confidence < CONFIDENCE_THRESHOLD:
        decision = {'action_type': 'manual_review',
                    'rationale': f'Classifier confidence {confidence:.4f} below threshold '
                                 f'{CONFIDENCE_THRESHOLD} (best guess: {specialist_slug}) -- may be a '
                                 f'genuinely novel topic the classifier cannot propose a new specialist for.'}
    else:
        decision = {'action_type': 'categorize_document', 'specialist_slug': specialist_slug,
                    'rationale': f'Classifier prediction, confidence={confidence:.4f}.'}
    # Always present, accepted or not -- the abstain case is where a human most wants the best guess.
    decision['predicted_slug'] = specialist_slug
    decision['confidence'] = confidence

    logger.info('classifier_triage doc=%s pred=%s confidence=%.4f', document_id, specialist_slug, confidence)
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
                (action_type, document_id, target_specialist_id, agent_rationale, source_backend)
                VALUES ('categorize_document', ?, ?, ?, 'classifier')''',
                (document_id, row['specialist_id'], decision['rationale'])
            )
            conn.commit()
            return
    # falls through here for manual_review, whether original or the fallback above
    conn.execute(
        "INSERT INTO pending_actions (action_type, document_id, agent_rationale, source_backend) "
        "VALUES ('manual_review', ?, ?, 'classifier')",
        (document_id, decision['rationale'])
    )
    conn.commit()