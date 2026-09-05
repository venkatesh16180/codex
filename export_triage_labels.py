# export_triage_labels.py
import json
from db import get_connection
from logging_setup import get_logger
 
logger = get_logger(__name__)

MAX_CHARS = 8000  # enough for topic signal without dumping full-book text;
                   # keeps forward-compat with a token-limited classifier later
 
def export_labels(conn, out_path='data/triage_labels.jsonl', max_chars=MAX_CHARS):
    rows = conn.execute(
        """SELECT DISTINCT sd.document_id, sd.title, sp.slug, sp.display_name
           FROM document_chunks dc
           JOIN specialist_chunks sc ON sc.chunk_id = dc.chunk_id
           JOIN specialists sp ON sp.specialist_id = sc.specialist_id
           JOIN source_documents sd ON sd.document_id = dc.document_id
           WHERE sd.triage_status = 'committed'
           ORDER BY sd.document_id"""
    ).fetchall()
 
    seen_documents = set()
    written = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for row in rows:
            if row['document_id'] in seen_documents:
                logger.warning(
                    'document_id=%s (%s) maps to more than one specialist -- skipped, needs manual review',
                    row['document_id'], row['title']
                )
                continue
            seen_documents.add(row['document_id'])
            chunks = conn.execute(
                'SELECT chunk_text FROM document_chunks WHERE document_id=? ORDER BY chunk_index',
                (row['document_id'],)
            ).fetchall()
            
            text_parts, total_len, truncated = [], 0, False
            for c in chunks:
                if total_len >= max_chars:
                    truncated = True
                    break
                text_parts.append(c['chunk_text'])
                total_len += len(c['chunk_text'])
            text = '\n\n'.join(text_parts)

            if truncated:
                logger.warning('document_id=%s (%s) truncated at %d chars', row['document_id'], row['title'], max_chars)

            f.write(json.dumps({
                'document_id': row['document_id'],
                'title': row['title'],
                'specialist_slug': row['slug'],
                'text': text,
                'text_truncated': truncated,
            }) + '\n')
            written += 1
 
    logger.info('triage_labels_exported count=%d path=%s', written, out_path)
    return written
 
if __name__ == '__main__':
    conn = get_connection()
    export_labels(conn)
    conn.close()
