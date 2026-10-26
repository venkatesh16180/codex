# test_chat_followup.py -- Phase 20
#
# Before Phase 20, a follow-up whose own text scored below the relevance floor
# ("what did you just say?") returned "This specialist doesn't have any approved
# material yet" without ever calling the model -- even when the specialist had plenty of
# material and the conversation history made the question answerable. Only the Ollama
# call and the embedding model are faked; retrieval, the floor and the database
# (an isolated in-memory one) are real.
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

import chat
from embeddings import serialize_embedding

ON_TOPIC = 'what is stoicism?'
FOLLOW_UP = 'what did you just say?'


def _unit(i):
    v = np.zeros(384, dtype=np.float32)
    v[i] = 1.0
    return v


def _embed_model():
    # ON_TOPIC matches the stored chunk exactly (score 1.0); everything else is orthogonal (0.0)
    model = MagicMock()
    model.encode.side_effect = lambda q: _unit(0) if q == ON_TOPIC else _unit(7)
    return model


def _setup(db, with_material=True):
    db.execute("INSERT INTO specialists (slug, display_name, scope_description) VALUES ('s', 'S', 'x')")
    if with_material:
        db.execute("INSERT INTO source_documents (file_path, file_hash, title, file_type) "
                   "VALUES ('_p', '_h', 'Meditations', 'txt')")
        db.execute("INSERT INTO document_chunks (document_id, chunk_index, chunk_text, embedding) "
                   "VALUES (1, 0, 'Stoicism teaches the dichotomy of control.', ?)",
                   (serialize_embedding(_unit(0)),))
        db.execute("INSERT INTO specialist_chunks (specialist_id, chunk_id) VALUES (1, 1)")
    db.commit()


def _fake_llm(monkeypatch):
    calls = []

    def fake(client, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content='MODEL ANSWER'))

    monkeypatch.setattr(chat, 'chat_with_retry', fake)
    return calls


HISTORY = [{'role': 'user', 'content': ON_TOPIC},
           {'role': 'assistant', 'content': 'Stoicism is about the dichotomy of control.'}]


def test_followup_below_floor_reuses_previous_questions_retrieval(fresh_db, monkeypatch):
    _setup(fresh_db)
    calls = _fake_llm(monkeypatch)
    answer = chat.chat_with_specialist(fresh_db, _embed_model(), 's', FOLLOW_UP, history=HISTORY)
    assert answer == 'MODEL ANSWER'
    assert len(calls) == 1
    messages = calls[0]['messages']
    assert '[Source: Meditations]' in messages[-1]['content']        # context from the previous question
    assert f'Question: {FOLLOW_UP}' in messages[-1]['content']       # but the user's real question
    assert messages[1:3] == HISTORY                                   # history still passed as real turns


def test_below_floor_without_history_says_no_match_not_no_material(fresh_db, monkeypatch):
    _setup(fresh_db)
    calls = _fake_llm(monkeypatch)
    answer = chat.chat_with_specialist(fresh_db, _embed_model(), 's', FOLLOW_UP)
    assert calls == []
    assert 'closely enough' in answer
    assert 'any approved material' not in answer


def test_specialist_with_no_material_keeps_the_no_material_message(fresh_db, monkeypatch):
    _setup(fresh_db, with_material=False)
    calls = _fake_llm(monkeypatch)
    answer = chat.chat_with_specialist(fresh_db, _embed_model(), 's', FOLLOW_UP, history=HISTORY)
    assert calls == []
    assert "doesn't have any approved material yet" in answer


def test_followup_is_refused_when_the_previous_question_is_off_topic_too(fresh_db, monkeypatch):
    _setup(fresh_db)
    calls = _fake_llm(monkeypatch)
    history = [{'role': 'user', 'content': 'what is the weather?'},
               {'role': 'assistant', 'content': 'No idea.'}]
    answer = chat.chat_with_specialist(fresh_db, _embed_model(), 's', FOLLOW_UP, history=history)
    assert calls == []
    assert 'closely enough' in answer


def test_relevant_question_is_unchanged(fresh_db, monkeypatch):
    _setup(fresh_db)
    calls = _fake_llm(monkeypatch)
    answer = chat.chat_with_specialist(fresh_db, _embed_model(), 's', ON_TOPIC)
    assert answer == 'MODEL ANSWER'
    assert len(calls) == 1
    assert '[Source: Meditations]' in calls[0]['messages'][-1]['content']


def test_web_on_but_empty_is_not_reported_as_web_search_off(fresh_db, monkeypatch):
    _setup(fresh_db)
    _fake_llm(monkeypatch)
    monkeypatch.setattr(chat, 'fetch_web_context', lambda q: '')
    answer = chat.chat_with_specialist(fresh_db, _embed_model(), 's', FOLLOW_UP, use_web=True)
    assert 'Web search returned nothing' in answer
    assert 'Web search is off' not in answer
