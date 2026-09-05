# train_baseline_classifier.py
import json, time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import accuracy_score, classification_report
from logging_setup import get_logger
 
logger = get_logger(__name__)
 
# Excluded: cannot evaluate a class with only 1 example under LOOCV.
# See Phase 10 BUILD-JOURNAL for why these two are singletons by decision, not oversight.
EXCLUDED_SLUGS = {'banking_ml', 'cognitivepsychology'}
 
def load_dataset(path='data/triage_labels.jsonl'):
    texts, labels, doc_ids = [], [], []
    with open(path, encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if row['specialist_slug'] in EXCLUDED_SLUGS:
                continue
            texts.append(row['text'])
            labels.append(row['specialist_slug'])
            doc_ids.append(row['document_id'])
    return texts, labels, doc_ids
 
def run_loocv(texts, labels, doc_ids):
    loo = LeaveOneOut()
    y_true, y_pred, per_doc, inference_times = [], [], [], []
 
    for train_idx, test_idx in loo.split(texts):
        train_texts = [texts[i] for i in train_idx]
        train_labels = [labels[i] for i in train_idx]
        test_text, test_label, test_doc_id = texts[test_idx[0]], labels[test_idx[0]], doc_ids[test_idx[0]]
 
        # A fresh vectorizer per fold -- fitting once on the full corpus first would leak
        # vocabulary from the held-out document into training, inflating the result.
        vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2), min_df=1, stop_words='english')
        X_train = vectorizer.fit_transform(train_texts)
        X_test = vectorizer.transform([test_text])
 
        clf = LogisticRegression(max_iter=1000, class_weight='balanced')
        clf.fit(X_train, train_labels)
 
        t0 = time.perf_counter()
        pred = clf.predict(X_test)[0]
        inference_times.append(time.perf_counter() - t0)
 
        y_true.append(test_label); y_pred.append(pred)
        per_doc.append({'document_id': test_doc_id, 'true': test_label,
                        'predicted': pred, 'correct': pred == test_label})
 
    return y_true, y_pred, per_doc, inference_times
 
if __name__ == '__main__':
    texts, labels, doc_ids = load_dataset()
    logger.info('baseline_classifier_dataset size=%d classes=%d', len(texts), len(set(labels)))
 
    y_true, y_pred, per_doc, inference_times = run_loocv(texts, labels, doc_ids)
    acc = accuracy_score(y_true, y_pred)
    avg_ms = 1000 * sum(inference_times) / len(inference_times)
    logger.info('baseline_classifier_loocv_accuracy=%.3f avg_inference_ms=%.2f', acc, avg_ms)
 
    print(classification_report(y_true, y_pred, zero_division=0))
    for r in per_doc:
        mark = 'OK ' if r['correct'] else 'ERR'
        print(f"{mark} doc={r['document_id']:>3} true={r['true']:<22} pred={r['predicted']}")
