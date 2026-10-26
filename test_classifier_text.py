# test_classifier_text.py -- Phase 20
#
# Before Phase 20 the classifier was trained on one text recipe (export_triage_labels.py:
# front matter included, chunks joined with blank lines) and served another
# (classifier_triage.py: front matter skipped, joined with spaces, sliced), so the LOOCV
# accuracy described text production never sent. Both now go through
# content_preview.build_classifier_text(); these tests keep them from drifting apart again.
import json
import re

import sklearn

import classifier_triage
from content_preview import CLASSIFIER_MAX_CHARS, build_classifier_text
from export_triage_labels import export_labels
from train_final_classifier import build_bundle

FRONT = 'Copyright 1997. All rights reserved. No part of this publication may be reproduced.'
BODY = 'Rich dads acquire assets while poor dads acquire liabilities, and the difference compounds over decades.'


def _chunks(*texts):
    return [{'chunk_text': t} for t in texts]


def _add_committed_document(db, n_front=3, n_body=6):
    db.execute("INSERT INTO specialists (slug, display_name, scope_description) "
               "VALUES ('test_spec', 'T', 'x')")
    db.execute("INSERT INTO source_documents (file_path, file_hash, title, file_type, triage_status) "
               "VALUES ('_p', '_h', 'Test Book', 'txt', 'committed')")
    texts = [FRONT] * n_front + [f'{BODY} chunk {i}' for i in range(n_body)]
    for i, text in enumerate(texts):
        db.execute("INSERT INTO document_chunks (document_id, chunk_index, chunk_text, embedding) "
                   "VALUES (1, ?, ?, ?)", (i, text, b''))
        db.execute("INSERT INTO specialist_chunks (specialist_id, chunk_id) VALUES (1, ?)", (i + 1,))
    db.commit()


def _tiny_bundle():
    texts = ['apples oranges bananas fruit basket market', 'pears grapes cherries fruit orchard market',
             'steel iron copper metal forge anvil', 'zinc nickel tin metal foundry anvil']
    return build_bundle(texts, ['fruit', 'fruit', 'metal', 'metal'], [1, 2, 3, 4])


def test_front_matter_is_skipped_and_text_is_capped():
    chunks = _chunks(FRONT, FRONT, FRONT, BODY, BODY, BODY, BODY)
    text, truncated = build_classifier_text(chunks, max_chars=10_000)
    assert 'Copyright' not in text
    assert not truncated
    assert text.count(BODY) == 4
    text, truncated = build_classifier_text(chunks, max_chars=50)
    assert len(text) <= 50
    assert truncated


def test_export_and_serving_build_identical_text(fresh_db, tmp_path):
    _add_committed_document(fresh_db)
    out = tmp_path / 'labels.jsonl'
    export_labels(fresh_db, out_path=str(out))
    row = json.loads(out.read_text(encoding='utf-8').splitlines()[0])
    chunks = fresh_db.execute(
        'SELECT chunk_text FROM document_chunks WHERE document_id=1 ORDER BY chunk_index').fetchall()
    expected, _ = build_classifier_text(chunks)
    assert row['text'] == expected
    assert 'Copyright' not in row['text']


def test_abstain_keeps_best_guess_with_four_decimals(fresh_db, monkeypatch):
    _add_committed_document(fresh_db)
    monkeypatch.setattr(classifier_triage, '_model_cache', _tiny_bundle())
    monkeypatch.setattr(classifier_triage, 'CONFIDENCE_THRESHOLD', 1.01)   # force an abstain
    decision = classifier_triage.classifier_triage(fresh_db, 1)
    assert decision['action_type'] == 'manual_review'
    assert decision['predicted_slug'] in {'fruit', 'metal'}
    assert 0 < decision['confidence'] <= 1
    assert decision['predicted_slug'] in decision['rationale']
    assert re.search(r'confidence \d\.\d{4} below', decision['rationale'])


def test_accepted_decision_carries_slug_and_confidence(fresh_db, monkeypatch):
    _add_committed_document(fresh_db)
    monkeypatch.setattr(classifier_triage, '_model_cache', _tiny_bundle())
    monkeypatch.setattr(classifier_triage, 'CONFIDENCE_THRESHOLD', 0.0)    # force an accept
    decision = classifier_triage.classifier_triage(fresh_db, 1)
    assert decision['action_type'] == 'categorize_document'
    assert decision['specialist_slug'] == decision['predicted_slug']
    assert re.search(r'confidence=\d\.\d{4}\.', decision['rationale'])


def test_saved_model_records_what_it_was_trained_on():
    meta = _tiny_bundle()['meta']
    assert meta['n_docs'] == 4
    assert meta['classes'] == ['fruit', 'metal']
    assert meta['doc_ids'] == [1, 2, 3, 4]
    assert meta['max_chars'] == CLASSIFIER_MAX_CHARS
    assert meta['sklearn_version'] == sklearn.__version__
    assert meta['trained_at']
