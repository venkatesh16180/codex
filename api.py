# api.py
import os, time, threading, uuid
os.environ['HF_HUB_OFFLINE'] = '1'
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from db import get_connection
from sentence_transformers import SentenceTransformer
from ingest import ingest_file
from agent import triage_document
from classifier_triage import classifier_triage, stage_classifier_decision

app = FastAPI()

# In-memory only -- lost on restart. Phase 17 (Concurrency-Safe Writes) needs to
# replace this with real persistence before this is genuinely production-ready.
JOBS = {}

_embed_model = None
def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embed_model


class SubmitRequest(BaseModel):
    file_path: str
    backend: str = 'llm'  # matches add_source.py --backend exactly


@app.post('/documents')
def submit_document(req: SubmitRequest):
    if req.backend not in ('llm', 'classifier'):
        raise HTTPException(400, "backend must be 'llm' or 'classifier'")

    conn = get_connection()
    try:
        document_id = ingest_file(req.file_path, conn)
    except Exception as e:
        conn.close()
        raise HTTPException(400, f'Failed to ingest file: {e}')
    conn.close()

    if document_id is None:
        raise HTTPException(400, 'Unsupported file type or already ingested -- nothing to triage.')

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'status': 'processing', 'document_id': document_id,
                     'backend': req.backend, 'started_at': time.time()}

    thread = threading.Thread(target=_run_triage, args=(job_id, document_id, req.backend), daemon=True)
    thread.start()

    return {'job_id': job_id, 'document_id': document_id, 'status': 'processing'}


@app.get('/documents/{job_id}')
def check_status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, 'Unknown job_id')

    response = dict(job)
    if job['status'] == 'processing':
        response['elapsed_sec'] = round(time.time() - job['started_at'], 1)
    return response


def _run_triage(job_id, document_id, backend):
    conn = get_connection()
    try:
        if backend == 'classifier':
            decision = classifier_triage(conn, document_id)
            stage_classifier_decision(conn, document_id, decision)
        else:
            triage_document(conn, get_embed_model(), document_id)
        JOBS[job_id]['status'] = 'complete'
        JOBS[job_id]['finished_at'] = time.time()
    except Exception as e:
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['error'] = str(e)
    finally:
        conn.close()