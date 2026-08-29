# add_source.py
import sys, glob, os
os.environ['HF_HUB_OFFLINE'] = '1'
from db import get_connection
from sentence_transformers import SentenceTransformer
from ingest import ingest_file
from agent import triage_document

def main(path_or_glob: str):
    conn = get_connection()
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')

    files = glob.glob(path_or_glob) if '*' in path_or_glob else [path_or_glob]
    staged = 0

    for path in files:
        document_id = ingest_file(path, conn)
        if document_id is None:
            continue  # unsupported type or already-ingested
        triage_document(conn, embed_model, document_id)
        staged += 1

    print(f'{staged} document(s) ingested and triaged.')
    print('Run `python review_pending.py` to approve or reject before anything goes live.')

if __name__ == '__main__':
    main(sys.argv[1])