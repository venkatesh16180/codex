# search.py
from embeddings import deserialize_embedding, cosine_similarity
import numpy as np

def search_specialist(conn, embed_model, specialist_id: int, query: str, top_k: int = 5):
    rows = conn.execute(
        '''SELECT dc.chunk_text, dc.embedding
           FROM specialist_chunks sc
           JOIN document_chunks dc ON dc.chunk_id = sc.chunk_id
           WHERE sc.specialist_id = ?''',
        (specialist_id,)
    ).fetchall()
    if not rows:
        return []
    vectors = np.stack([deserialize_embedding(r['embedding']) for r in rows])
    query_vec = embed_model.encode(query)
    scores = cosine_similarity(query_vec, vectors)
    top = np.argsort(scores)[::-1][:top_k]
    return [{'text': rows[i]['chunk_text'], 'score': float(scores[i])} for i in top]