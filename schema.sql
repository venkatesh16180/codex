PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE specialists (
    specialist_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    scope_description TEXT NOT NULL,
    persona_style   TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at     TEXT
);

CREATE TABLE source_documents (
    document_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT NOT NULL,
    file_hash       TEXT UNIQUE NOT NULL,
    title           TEXT,
    file_type       TEXT NOT NULL,
    ingested_at     TEXT NOT NULL DEFAULT (datetime('now')),
    triage_status   TEXT NOT NULL DEFAULT 'untriaged'
);

CREATE TABLE document_chunks (
    chunk_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES source_documents(document_id),
    chunk_index     INTEGER NOT NULL,
    chunk_text      TEXT NOT NULL,
    embedding       BLOB NOT NULL,
    UNIQUE(document_id, chunk_index)
);

CREATE TABLE specialist_chunks (
    specialist_id   INTEGER NOT NULL REFERENCES specialists(specialist_id),
    chunk_id        INTEGER NOT NULL REFERENCES document_chunks(chunk_id),
    committed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (specialist_id, chunk_id)
);

CREATE TABLE pending_actions (
    action_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type                TEXT NOT NULL,
    document_id                 INTEGER REFERENCES source_documents(document_id),
    target_specialist_id         INTEGER REFERENCES specialists(specialist_id),
    proposed_specialist_slug      TEXT,
    proposed_specialist_description TEXT,
    agent_rationale                TEXT NOT NULL,
    status                          TEXT NOT NULL DEFAULT 'pending',
    created_at                      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at                     TEXT,
    resolver_note                   TEXT
);