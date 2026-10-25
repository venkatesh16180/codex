# add_source.py
import sys, glob, os, argparse
os.environ['HF_HUB_OFFLINE'] = '1'
from db import get_connection
from sentence_transformers import SentenceTransformer
from ingest import ingest_file
from agent import triage_document
from classifier_triage import classifier_triage, stage_classifier_decision
from logging_setup import get_logger

logger = get_logger(__name__)

def main(path_or_glob: str, backend: str = 'llm'):
    conn = get_connection()
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    files = glob.glob(path_or_glob) if '*' in path_or_glob else [path_or_glob]
    staged = 0
    failed = []   # (document_id, path, error) -- ingested but NOT triaged

    for path in files:
        document_id = ingest_file(path, conn)
        if document_id is None:
            continue  # unsupported type or already-ingested
        try:
            if backend == 'classifier':
                decision = classifier_triage(conn, document_id)
                stage_classifier_decision(conn, document_id, decision)
            else:
                triage_document(conn, embed_model, document_id)
        except Exception as e:
            # One bad document must not stop the batch. But it is already ingested, so
            # rerunning this script would skip it (hash dedup) -- report that plainly.
            logger.error('triage_failed document_id=%s path=%s error=%s', document_id, path, e)
            failed.append((document_id, path, e))
            if isinstance(e, ConnectionError):
                print('Ollama is unreachable (retries exhausted) -- stopping the batch '
                      'instead of ingesting more documents that cannot be triaged.')
                break
            continue
        staged += 1

    print(f'{staged} document(s) ingested and triaged.')
    if failed:
        print(f'{len(failed)} document(s) ingested but NOT triaged (rerunning this command will skip them):')
        for document_id, path, e in failed:
            print(f'  document_id={document_id}  {path}  -- {type(e).__name__}: {e}')
        print('Re-triage them with dev_checks/retriage_orphaned.py.')
    print('Run `python review_pending.py` to approve or reject before anything goes live.')
    if failed:
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pattern', help='File path or glob pattern, e.g. "data\\test_library\\*"')
    parser.add_argument('--backend', choices=['llm', 'classifier'], default='llm',
        help="llm: slow (~20-40+ min/doc), most accurate, can propose new specialists "
             "(default). classifier: near-instant, lower accuracy, cannot propose new "
             "specialists -- use for bulk batches where a multi-hour LLM run is undesirable.")
    args = parser.parse_args()
    main(args.pattern, backend=args.backend)