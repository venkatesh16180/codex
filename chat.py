# chat.py
import ollama
from search import search_specialist  # reuses Phase 3's function as-is
from web_search import fetch_web_context
# chat.py -- was: CHAT_MODEL / HISTORY_TURNS / RELEVANCE_THRESHOLD as module constants
from config import CHAT_MODEL, HISTORY_TURNS, RELEVANCE_THRESHOLD, NUM_CTX


# CHAT_MODEL = 'llama3.2'  # deliberately NOT the tool-calling model -- see note below
# HISTORY_TURNS = 3  # how many prior question/answer pairs to feed back in -- tune here
# RELEVANCE_THRESHOLD = 0.3  # same noise floor Phase 3's isolation test used to
                            # distinguish real matches from cross-topic scores
# was silently defaulting to 2048 -- see BUILD-JOURNAL.md

def build_persona_prompt(specialist: dict, web_enabled: bool = False) -> str:
    base = f"You are {specialist['display_name']}. {specialist['persona_style'] or ''}\n\n"

    grounding_scope = (
        'This grounding rule applies specifically to factual or advice-seeking '
        'questions about the library material -- it does not restrict you from '
        'using the recent conversation history shown to you separately, for '
        'follow-up questions or requests that refer back to something already '
        'said in this chat.\n\n'
    )

    if web_enabled:
        return base + grounding_scope + (
            'Ground your answer in the LOCAL LIBRARY CONTEXT first. If it is thin or '
            'missing, you may also draw on the WEB CONTEXT below -- but say plainly when '
            "you're doing so, e.g. 'Your library doesn't cover this directly, but...'. "
            'Never blend the two without distinguishing them. Each local passage is '
            'labeled with its source title -- if you reference or rely on a passage, '
            'name that title rather than leaving the source unstated.'
        )
    else:
        return base + grounding_scope + (
            'Answer ONLY using the LOCAL LIBRARY CONTEXT below. If the context does not '
            "contain enough to answer, say so plainly rather than guessing or drawing on "
            "general knowledge. Each passage is labeled with its source title -- if you "
            "reference or rely on a passage, name that title rather than leaving the "
            "source unstated."
        )

# chat.py (continued)

def chat_with_specialist(conn, embed_model, specialist_slug: str, user_query: str,
                          top_k: int = 5, use_web: bool = False, history: list | None = None) -> str:
    specialist = conn.execute(
        'SELECT * FROM specialists WHERE slug=?', (specialist_slug,)
    ).fetchone()

    local = search_specialist(conn, embed_model, specialist['specialist_id'], user_query, top_k)
    # A query with no real informational content (e.g. "remember this number: 12")
    # can still return the top_k nearest chunks by cosine distance -- nearest
    # isn't the same as relevant. If even the best match falls below the noise
    # floor, treat this turn as having no local context at all, rather than
    # handing the model irrelevant chunks it's instructed to answer strictly from.
    if local and local[0]['score'] < RELEVANCE_THRESHOLD:
        local = []
    local_context = '\n\n---\n\n'.join(
        f"[Source: {r['source_title']}]\n{r['text']}" for r in local
    )

    web_context = fetch_web_context(user_query) if use_web else ''

    if not local_context and not web_context:
        return "This specialist doesn't have any approved material yet, and web search is off."

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

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=messages,
        options={'num_ctx': NUM_CTX}  
    )
    return response.message.content