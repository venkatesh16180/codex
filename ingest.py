# ingest.py
import hashlib, os
os.environ['HF_HUB_OFFLINE'] = '1'
from sentence_transformers import SentenceTransformer
from extract import EXTRACTORS
from chunk import chunk_text
from embeddings import serialize_embedding

embed_model = SentenceTransformer('all-MiniLM-L6-v2')

def file_hash(path: str) -> str:
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def ingest_file(path: str, conn) -> int | None:
    ext = os.path.splitext(path)[1].lower()
    if ext not in EXTRACTORS:
        print(f'Skipping unsupported type: {path}')
        return None

    h = file_hash(path)
    existing = conn.execute(
        'SELECT document_id FROM source_documents WHERE file_hash = ?', (h,)
    ).fetchone()
    if existing:
        return None   # already ingested

    try:
        text = EXTRACTORS[ext](path)
    except Exception as e:
        print(f'Extraction failed for {path}: {e}')
        return None

    cur = conn.execute(
        'INSERT INTO source_documents (file_path, file_hash, title, file_type) VALUES (?, ?, ?, ?)',
        (path, h, os.path.basename(path), ext.lstrip('.'))
    )
    document_id = cur.lastrowid

    for i, chunk in enumerate(chunk_text(text)):
        vec = embed_model.encode(chunk)
        conn.execute(
            'INSERT INTO document_chunks (document_id, chunk_index, chunk_text, embedding) VALUES (?, ?, ?, ?)',
            (document_id, i, chunk, serialize_embedding(vec))
        )
    conn.commit()
    return document_id