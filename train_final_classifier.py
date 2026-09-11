# train_final_classifier.py
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from train_baseline_classifier import load_dataset
from logging_setup import get_logger

logger = get_logger(__name__)
MODEL_PATH = 'data/triage_classifier.joblib'

if __name__ == '__main__':
    texts, labels, doc_ids = load_dataset()
    vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2), min_df=1, stop_words='english')
    X = vectorizer.fit_transform(texts)
    clf = LogisticRegression(max_iter=1000, class_weight='balanced')
    clf.fit(X, labels)

    joblib.dump({'vectorizer': vectorizer, 'classifier': clf}, MODEL_PATH)
    logger.info('classifier_persisted path=%s n_docs=%d n_classes=%d', MODEL_PATH, len(texts), len(set(labels)))
    print(f"Saved to {MODEL_PATH}. Expected accuracy (Phase 11 LOOCV): 72.7% -- "
          f"this exact artifact isn't independently re-tested, since no held-out "
          f"data remains once trained on everything.")