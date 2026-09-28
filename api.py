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

# In-memory only -- lost on restart. Phase 17 adds a persisted `jobs` table
# (see migrate_add_jobs.py) alongside this dict: JOBS stays the fast path
# for elapsed_sec on an actively-processing job, `jobs` is what lets a
# job's final state survive a restart. check_status() reads JOBS first and
# only falls back to the DB if the process has restarted since the job
# was submitted.
JOBS = {}

# Phase 17: how old a still-"processing" jobs row is allowed to be before
# startup reconciliation assumes the server crashed mid-job and marks it
# error rather than leaving it stuck at "processing" forever. A job
# genuinely still running when the server died has no other way to signal
# that -- nothing updates its row after the crash, so this is a deliberate
# cleanup pass, not a guess about whether it "might still be running"
# somewhere. Could move to config.py to match Phase 9's convention if this
# needs tuning later; kept local for now since it's new and untested.
STALE_JOB_THRESHOLD_SEC = 3 * 3600  # 3hr -- matches LLM_TRIAGE_TIMEOUT_SEC's
                                     # own ceiling (Phase 14), since a real
                                     # llm-backend triage call can legitimately
                                     # run close to that long


@app.on_event('startup')
def reconcile_stale_jobs():
    """Runs once when the API server starts. Any `jobs` row still marked
    'processing' from before this restart has no way to know the server
    died -- nothing else will ever update it. Sweep those rows to 'error'
    here rather than leaving them stuck at 'processing' indefinitely."""
    conn = get_connection()
    now = time.time()
    cutoff = now - STALE_JOB_THRESHOLD_SEC
    stale = conn.execute(
        "SELECT job_id FROM jobs WHERE status='processing' AND started_at < ?",
        (cutoff,)
    ).fetchall()
    if stale:
        conn.execute(
            "UPDATE jobs SET status='error', error=?, finished_at=? "
            "WHERE status='processing' AND started_at < ?",
            (f'Marked error on startup reconciliation -- still "processing" after '
             f'{STALE_JOB_THRESHOLD_SEC}s, server likely restarted mid-job.', now, cutoff)
        )
        conn.commit()
        print(f'Startup reconciliation: marked {len(stale)} stale job(s) as error.')
    conn.close()


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

    if document_id is None:
        conn.close()
        raise HTTPException(400, 'Unsupported file type or already ingested -- nothing to triage.')

    job_id = str(uuid.uuid4())
    started_at = time.time()
    JOBS[job_id] = {'status': 'processing', 'document_id': document_id,
                     'backend': req.backend, 'started_at': started_at}

    # Phase 17: persist immediately, same connection as the ingest call
    # above -- if the process dies before _run_triage's finally block runs,
    # this row still records the job was submitted, not just in-memory
    # state that vanishes with the process.
    conn.execute(
        'INSERT INTO jobs (job_id, document_id, backend, status, started_at) VALUES (?, ?, ?, ?, ?)',
        (job_id, document_id, req.backend, 'processing', started_at)
    )
    conn.commit()
    conn.close()  # done with this connection -- the background thread opens its own

    thread = threading.Thread(target=_run_triage, args=(job_id, document_id, req.backend), daemon=True)
    thread.start()

    return {'job_id': job_id, 'document_id': document_id, 'status': 'processing'}


@app.get('/documents/{job_id}')
def check_status(job_id: str):
    job = JOBS.get(job_id)
    if job is not None:
        response = dict(job)
        if job['status'] == 'processing':
            response['elapsed_sec'] = round(time.time() - job['started_at'], 1)
        return response

    # Phase 17: not in memory -- either a genuinely unknown job_id, or a
    # job that outlived a server restart. Fall back to the persisted table
    # before giving up.
    conn = get_connection()
    row = conn.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, 'Unknown job_id')

    response = dict(row)
    # No live elapsed_sec here -- we don't know if a restarted server's
    # background thread is still actually running this job or died with
    # the old process. reconcile_stale_jobs() is what eventually resolves
    # a truly-orphaned row to 'error'; until then, be honest that this is
    # recovered state, not a live status.
    response['note'] = ('Recovered from persisted state after a server restart -- '
                         'live progress is not available for this job.')
    return response


def _run_triage(job_id, document_id, backend):
    conn = get_connection()
    try:
        if backend == 'classifier':
            decision = classifier_triage(conn, document_id)
            stage_classifier_decision(conn, document_id, decision)
        else:
            triage_document(conn, get_embed_model(), document_id)
        finished_at = time.time()
        JOBS[job_id]['status'] = 'complete'
        JOBS[job_id]['finished_at'] = finished_at
        # Phase 17: mirror the same terminal state into the persisted table.
        conn.execute("UPDATE jobs SET status='complete', finished_at=? WHERE job_id=?",
                     (finished_at, job_id))
        conn.commit()
    except Exception as e:
        finished_at = time.time()
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['error'] = str(e)
        conn.execute("UPDATE jobs SET status='error', error=?, finished_at=? WHERE job_id=?",
                     (str(e), finished_at, job_id))
        conn.commit()
    finally:
        conn.close()