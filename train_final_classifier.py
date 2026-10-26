# train_final_classifier.py
import joblib
from datetime import datetime, timezone

import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from train_baseline_classifier import load_dataset, EXCLUDED_SLUGS
from content_preview import CLASSIFIER_MAX_CHARS
from logging_setup import get_logger

logger = get_logger(__name__)
MODEL_PATH = 'data/triage_classifier.joblib'


def build_bundle(texts, labels, doc_ids):
    """Fit the final model and return the artifact to persist. The 'meta' block records
    what this model was trained on, so a later prediction can be traced to the model
    that made it, and a scikit-learn or text-prep mismatch can be noticed instead of
    silently shifting confidences (Phase 19's verification saw one document cross the
    threshold between scikit-learn 1.8.0 and 1.9.0)."""
    vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2), min_df=1, stop_words='english')
    X = vectorizer.fit_transform(texts)
    clf = LogisticRegression(max_iter=1000, class_weight='balanced')
    clf.fit(X, labels)
    return {
        'vectorizer': vectorizer,
        'classifier': clf,
        'meta': {
            'n_docs': len(texts),
            'classes': sorted(set(labels)),
            'doc_ids': list(doc_ids),
            'excluded_slugs': sorted(EXCLUDED_SLUGS),
            'max_chars': CLASSIFIER_MAX_CHARS,
            'sklearn_version': sklearn.__version__,
            'trained_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        },
    }


if __name__ == '__main__':
    texts, labels, doc_ids = load_dataset()
    bundle = build_bundle(texts, labels, doc_ids)
    joblib.dump(bundle, MODEL_PATH)
    logger.info('classifier_persisted path=%s n_docs=%d n_classes=%d', MODEL_PATH, len(texts), len(set(labels)))
    print(f"Saved to {MODEL_PATH} ({len(texts)} documents, {len(set(labels))} classes). "
          f"This exact artifact isn't independently re-tested, since no held-out data remains "
          f"once trained on everything; run train_baseline_classifier.py for the current LOOCV accuracy.")
