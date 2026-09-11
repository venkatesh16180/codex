# add_source.py
import sys, glob, os, argparse
os.environ['HF_HUB_OFFLINE'] = '1'
from db import get_connection
from sentence_transformers import SentenceTransformer
from ingest import ingest_file
from agent import triage_document
from classifier_triage import classifier_triage, stage_classifier_decision

def main(path_or_glob: str, backend: str = 'llm'):
    conn = get_connection()
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    files = glob.glob(path_or_glob) if '*' in path_or_glob else [path_or_glob]
    staged = 0

    for path in files:
        document_id = ingest_file(path, conn)
        if document_id is None:
            continue  # unsupported type or already-ingested
        if backend == 'classifier':
            decision = classifier_triage(conn, document_id)
            stage_classifier_decision(conn, document_id, decision)
        else:
            triage_document(conn, embed_model, document_id)
        staged += 1

    print(f'{staged} document(s) ingested and triaged.')
    print('Run `python review_pending.py` to approve or reject before anything goes live.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pattern', help='File path or glob pattern, e.g. "data\\test_library\\*"')
    parser.add_argument('--backend', choices=['llm', 'classifier'], default='llm',
        help="llm: slow (~20-40+ min/doc), most accurate, can propose new specialists "
             "(default). classifier: near-instant, lower accuracy, cannot propose new "
             "specialists -- use for bulk batches where a multi-hour LLM run is undesirable.")
    args = parser.parse_args()
    main(args.pattern, backend=args.backend)