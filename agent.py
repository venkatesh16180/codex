# agent.py
import ollama
import numpy as np
from embeddings import deserialize_embedding, cosine_similarity

LIBRARIAN_MODEL = 'qwen3:4b'
TERMINAL_TOOLS = {'propose_categorization', 'propose_new_specialist', 'flag_for_manual_review'}

SYSTEM_PROMPT = '''You are the Librarian for a personal document collection. Given one
document, decide which specialist knowledge base it belongs in, or propose a new
specialist if nothing fits, or flag it for manual review if you're not confident.
Always check list_specialists() before deciding. Use search_similar_chunks to check
for precedent when a document's fit is ambiguous. Conclude with exactly one of:
propose_categorization, propose_new_specialist, or flag_for_manual_review.

When you call propose_new_specialist, also draft a short persona_style: 2-3
comma-separated traits describing how this specialist should sound when answering
chat questions later. This is a first draft a human reviewer will read, edit, or
discard -- a reasonable attempt is enough, it does not need to be perfect. Match the
house style of existing specialists' persona_style values, shown to you by
list_specialists() when they're set.'''

def make_tools(conn, document_id, embed_model):
    # document_id is a closure variable here, NOT a parameter of any function below --
    # the model can never see or set it, only the specialist_slug/rationale it's actually deciding.

    def list_specialists() -> list[dict]:
        """List all active specialists, what each one's knowledge base covers, and
        (when set) its persona_style, so a new proposal's persona can match house style."""
        rows = conn.execute(
            "SELECT slug, display_name, scope_description, persona_style FROM specialists WHERE status='active'"
        ).fetchall()
        out = []
        for r in rows:
            d = {'slug': r['slug'], 'display_name': r['display_name'], 'scope_description': r['scope_description']}
            if r['persona_style']:
                d['persona_style'] = r['persona_style']
            out.append(d)
        return out

    def search_similar_chunks(query: str, top_k: int = 5) -> list[dict]:
        """Search already-committed material for passages similar to a query, to check
        for precedent before deciding where this document belongs."""
        rows = conn.execute(
            '''SELECT s.slug, dc.chunk_text, dc.embedding
               FROM specialist_chunks sc
               JOIN document_chunks dc ON dc.chunk_id = sc.chunk_id
               JOIN specialists s ON s.specialist_id = sc.specialist_id'''
        ).fetchall()
        if not rows:
            return []
        vectors = np.stack([deserialize_embedding(r['embedding']) for r in rows])
        scores = cosine_similarity(embed_model.encode(query), vectors)
        top = np.argsort(scores)[::-1][:top_k]
        return [{'specialist': rows[i]['slug'], 'snippet': rows[i]['chunk_text'][:300]} for i in top]

    def propose_categorization(specialist_slug: str, rationale: str) -> str:
        """Propose this document be added to a specialist's knowledge base.
        Args: specialist_slug: an existing slug from list_specialists().
              rationale: a short explanation a human reviewer will read."""
        row = conn.execute(
            "SELECT specialist_id FROM specialists WHERE slug=? AND status='active'",
            (specialist_slug,)
        ).fetchone()
        if row is None:
            return f"ERROR: No active specialist '{specialist_slug}'. Call list_specialists() first."
        conn.execute(
            '''INSERT INTO pending_actions
               (action_type, document_id, target_specialist_id, agent_rationale)
               VALUES ('categorize_document', ?, ?, ?)''',
            (document_id, row['specialist_id'], rationale)
        )
        conn.commit()
        return 'Staged for human review. Nothing has been committed yet.'

    def propose_new_specialist(slug: str, display_name: str, scope_description: str,
                                persona_style: str, rationale: str) -> str:
        """Propose a new specialist when this document fits nothing on the current roster.
        Args: persona_style: a draft, 2-3 comma-separated traits for how this specialist
              should sound in chat -- a human will review and may edit or discard it."""
        conn.execute(
            '''INSERT INTO pending_actions
               (action_type, document_id, proposed_specialist_slug,
                proposed_specialist_description, proposed_persona_style, agent_rationale)
               VALUES ('propose_specialist', ?, ?, ?, ?, ?)''',
            (document_id, slug, scope_description, persona_style, rationale)
        )
        conn.commit()
        return 'New specialist proposal staged for human review.'

    def flag_for_manual_review(rationale: str) -> str:
        """Abstain: stage this document for a human to decide by hand."""
        conn.execute(
            "INSERT INTO pending_actions (action_type, document_id, agent_rationale) VALUES ('manual_review', ?, ?)",
            (document_id, rationale)
        )
        conn.commit()
        return 'Flagged for manual review.'

    return [list_specialists, search_similar_chunks, propose_categorization,
            propose_new_specialist, flag_for_manual_review]


def triage_document(conn, embed_model, document_id: int, max_iterations: int = 6):
    doc = conn.execute(
        'SELECT title, file_type FROM source_documents WHERE document_id=?', (document_id,)
    ).fetchone()
    preview = ' '.join(r['chunk_text'] for r in conn.execute(
        'SELECT chunk_text FROM document_chunks WHERE document_id=? ORDER BY chunk_index LIMIT 3',
        (document_id,)
    ).fetchall())

    tools = make_tools(conn, document_id, embed_model)
    tools_by_name = {t.__name__: t for t in tools}
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content':
            f"Title: {doc['title']}\nType: {doc['file_type']}\nPreview:\n{preview[:1500]}"}
    ]

    for _ in range(max_iterations):
        response = ollama.chat(model=LIBRARIAN_MODEL, messages=messages, tools=tools, think=True)
        messages.append(response.message)

        if not response.message.tool_calls:
            messages.append({'role': 'user',
                'content': 'Please conclude using one of your tools, not plain text.'})
            continue

        for call in response.message.tool_calls:
            print(f'  -> called {call.function.name}({call.function.arguments})')
            fn = tools_by_name.get(call.function.name)
            result = fn(**call.function.arguments) if fn else f'Unknown tool: {call.function.name}'
            messages.append({'role': 'tool', 'tool_name': call.function.name, 'content': str(result)})
            # Only treat a terminal-tool call as actually terminal if it succeeded --
            # propose_categorization can fail validation (bad slug) and return an
            # ERROR: string instead of staging anything; that must fall through to
            # the next loop iteration, not end triage with nothing staged.
            if call.function.name in TERMINAL_TOOLS and not str(result).startswith('ERROR:'):
                return

    tools_by_name['flag_for_manual_review'](
        rationale='Agent did not reach a decision within the iteration limit.'
    )