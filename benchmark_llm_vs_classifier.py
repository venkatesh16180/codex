# benchmark_llm_vs_classifier.py
import json, time, os
from db import get_connection
from sentence_transformers import SentenceTransformer
from agent import triage_document
from train_baseline_classifier import load_dataset
from logging_setup import get_logger

logger = get_logger(__name__)
RESULTS_PATH = 'data/llm_benchmark_results.jsonl'


def already_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                done.add(json.loads(line)['document_id'])
    return done


if __name__ == '__main__':
    conn = get_connection()
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    # texts from load_dataset() aren't passed to triage_document -- it builds its own
    # preview internally from document_chunks (first 3 chunks, ~1500 chars). Only
    # labels and doc_ids from this call are actually used here.
    texts, labels, doc_ids = load_dataset()
    done = already_done(RESULTS_PATH)

    with open(RESULTS_PATH, 'a', encoding='utf-8') as f:
        for label, doc_id in zip(labels, doc_ids):
            if doc_id in done:
                continue

            t0 = time.perf_counter()
            decision = triage_document(conn, embed_model, doc_id, dry_run=True)
            elapsed = time.perf_counter() - t0

            proposed_slug = decision.get('specialist_slug') if decision else None

            result = {
                'document_id': doc_id,
                'true': label,
                'predicted': proposed_slug,
                'correct': proposed_slug == label,
                'latency_sec': elapsed,
                'action_type': decision.get('action_type') if decision else None,
            }
            f.write(json.dumps(result) + '\n')
            f.flush()  # write immediately -- don't lose a 30+ minute result to a crash
            logger.info('llm_benchmark doc=%s true=%s pred=%s latency=%.1fs',
                        doc_id, label, proposed_slug, elapsed)

    conn.close()