# web_search.py
from ddgs import DDGS  # pip install ddgs (renamed from duckduckgo-search)

def fetch_web_context(query: str, max_results: int = 4) -> str:
    '''Best-effort web snippets. Returns "" on failure rather than raising --
    this is a supplementary source, not something the chat should crash over.'''
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return ''

    if not results:
        return ''

    return '\n\n---\n\n'.join(f"{r['title']}\n{r.get('body', '')}" for r in results)