# chat.py
import httpx
import ollama
from search import search_specialist  # reuses Phase 3's function as-is
from web_search import fetch_web_context
from config import CHAT_MODEL, HISTORY_TURNS, RELEVANCE_THRESHOLD, NUM_CTX, LLM_CHAT_TIMEOUT_SEC, LLM_CONNECT_TIMEOUT_SEC
from ollama_retry import chat_with_retry  # Phase 14
from logging_setup import get_logger

logger = get_logger(__name__)

# Phase 14: a single client, built once at import time, used for every chat call.
# LLM_CHAT_TIMEOUT_SEC is the READ timeout only (set in config.py / .env), and the
# user is waiting on this path, so it is kept far shorter than the triage timeout.
# Same connect/read split rationale as agent.py's _triage_client.
_chat_client = ollama.Client(timeout=httpx.Timeout(
    connect=LLM_CONNECT_TIMEOUT_SEC,
    read=LLM_CHAT_TIMEOUT_SEC,
    write=LLM_CONNECT_TIMEOUT_SEC,
    pool=LLM_CONNECT_TIMEOUT_SEC,
))

def build_persona_prompt(specialist: dict, web_enabled: bool = False) -> str:
    base = f"You are {specialist['display_name']}. {specialist['persona_style'] or ''}\n\n"

    grounding_scope = (
        'This grounding rule applies specifically to factual or advice-seeking '
        'questions about the library material -- it does not restrict you from '
        'using the recent conversation history shown to you separately, for '
        'follow-up questions or requests that refer back to something already '
        'said in this chat.\n\n'
    )

    no_outside_knowledge = (
        'Do not mention any name, fact, quote, page number, or claim that is not '
        'explicitly present in the context provided below -- even if you believe '
        "it to be true from your own general knowledge. If you are not sure whether "
        'something appears in the context, treat it as absent rather than including '
        "it. It is always better to say the context doesn't cover something than to "
        'state a plausible-sounding detail that is not actually there.\n\n'
    )

    if web_enabled:
        return base + grounding_scope + no_outside_knowledge + (
            'Ground your answer in the LOCAL LIBRARY CONTEXT first. If it is thin or '
            'missing, you may also draw on the WEB CONTEXT below -- but say plainly when '
            "you're doing so, e.g. 'Your library doesn't cover this directly, but...'. "
            'Never blend the two without distinguishing them. Each local passage is '
            'labeled with its source title -- if you reference or rely on a passage, '
            'name that title rather than leaving the source unstated.'
        )
    else:
        return base + grounding_scope + no_outside_knowledge + (
            'Answer ONLY using the LOCAL LIBRARY CONTEXT below. If the context does not '
            "contain enough to answer, say so plainly rather than guessing or drawing on "
            "general knowledge. Each passage is labeled with its source title -- if you "
            "reference or rely on a passage, name that title rather than leaving the "
            "source unstated."
        )

# chat.py (continued)

def _fmt_score(score) -> str:
    return 'n/a' if score is None else f'{score:.4f}'


def _retrieve_local(conn, embed_model, specialist_id: int, query: str, top_k: int) -> tuple:
    """Scoped search plus the relevance floor.

    A query with no real informational content (e.g. "remember this number: 12")
    can still return the top_k nearest chunks by cosine distance -- nearest isn't the
    same as relevant. If even the best match falls below the noise floor, treat it as
    no local context at all, rather than handing the model irrelevant chunks it's
    instructed to answer strictly from.

    Returns (chunks, best_score). chunks is [] when the best match is below the floor;
    best_score is the raw top similarity (None if nothing is indexed), returned so the
    caller can log it -- the floor is a borrowed heuristic, and these logs are the data
    for tuning it."""
    local = search_specialist(conn, embed_model, specialist_id, query, top_k)
    best = local[0]['score'] if local else None
    if local and best < RELEVANCE_THRESHOLD:
        return [], best
    return local, best


def _last_user_question(history: list | None) -> str | None:
    for message in reversed(history or []):
        if message.get('role') == 'user':
            return message['content']
    return None


def chat_with_specialist(conn, embed_model, specialist_slug: str, user_query: str,
                          top_k: int = 5, use_web: bool = False, history: list | None = None) -> str:
    specialist = conn.execute(
        'SELECT * FROM specialists WHERE slug=?', (specialist_slug,)
    ).fetchone()

    local, top_score = _retrieve_local(conn, embed_model, specialist['specialist_id'], user_query, top_k)
    fallback_score = None
    if not local:
        # A follow-up ("what did you just say?", "where was that from?") has almost no
        # content of its own, so it falls below the relevance floor even though the
        # conversation is squarely about this specialist's material. Before Phase 20 that
        # returned a canned message without ever calling the model, so the history
        # was never used. Retrieve with the previous question instead; the model still
        # decides whether that context answers the follow-up.
        previous = _last_user_question(history)
        if previous:
            local, fallback_score = _retrieve_local(conn, embed_model, specialist['specialist_id'], previous, top_k)
    logger.info('chat_retrieval specialist=%s top_score=%s floor=%.2f followup_fallback=%s fallback_score=%s',
                specialist_slug, _fmt_score(top_score), RELEVANCE_THRESHOLD,
                fallback_score is not None and bool(local), _fmt_score(fallback_score))
    local_context = '\n\n---\n\n'.join(
        f"[Source: {r['source_title']}]\n{r['text']}" for r in local
    )

    web_context = fetch_web_context(user_query) if use_web else ''

    if not local_context and not web_context:
        tail = ' Web search is off.' if not use_web else ' Web search returned nothing either.'
        has_material = conn.execute(
            'SELECT 1 FROM specialist_chunks WHERE specialist_id=? LIMIT 1',
            (specialist['specialist_id'],)
        ).fetchone()
        if has_material is None:
            return f"This specialist doesn't have any approved material yet.{tail}"
        # The specialist has material; nothing in it is close enough to this question.
        return ("Nothing in this specialist's approved material matches that question "
                f"closely enough to answer from it.{tail} Try rephrasing it.")

    parts = []
    if local_context:
        parts.append(f'LOCAL LIBRARY CONTEXT:\n{local_context}')
    if web_context:
        parts.append(f'WEB CONTEXT (outside the local library):\n{web_context}')

    messages = [{'role': 'system', 'content': build_persona_prompt(specialist, web_enabled=use_web)}]
    # Last HISTORY_TURNS exchanges, oldest first -- real prior turns, not more
    # retrieved context, so the model can answer "what was the second point?"
    # instead of treating every message as a standalone question.
    messages.extend(history or [])
    messages.append({'role': 'user', 'content': f"{chr(10).join(parts)}\n\nQuestion: {user_query}"})

    # Phase 14: was ollama.chat(model=CHAT_MODEL, ...) -- routed through the
    # module-level _chat_client (real timeouts, short since this is user-facing)
    # and chat_with_retry (retries connection errors, never retries a real timeout).
    response = chat_with_retry(
        _chat_client,
        model=CHAT_MODEL,
        messages=messages,
        options={'num_ctx': NUM_CTX}  # Ollama's default of 2048 silently truncated context -- see BUILD-JOURNAL.md
    )
    return response.message.content