# content_preview.py -- shared by agent.py and classifier_triage.py. Both previously
# took chunks from the raw start of a document with no front-matter awareness --
# same bug class (confirmed live on Rich Dad Poor Dad, document_id=29: the LLM's
# 3-chunk preview landed entirely on copyright/legal boilerplate and produced a
# nonsensical 'legal_disclaimers' specialist proposal). Fixed once, here, rather
# than patched separately in each caller.

FRONT_MATTER_MARKERS = [
    'isbn', 'all rights reserved', 'no part of this publication',
    'first edition', 'printed in', 'library of congress',
    'specifically disclaim', 'cover photo credit',
    'purchase this book without a cover', 'stolen property',
]


def looks_like_front_matter(text: str) -> bool:
    lower = text.lower()
    if any(marker in lower for marker in FRONT_MATTER_MARKERS):
        return True
    # A raw table-of-contents page-number dump has very few real letters --
    # catches numeric TOC chunks that no keyword would match.
    alpha_chars = sum(c.isalpha() for c in text)
    return len(text) > 0 and alpha_chars / len(text) < 0.5


def find_real_content_start(chunks: list, min_consecutive_clean: int = 3) -> int:
    """Return the index of the first chunk in a run of min_consecutive_clean
    chunks that don't look like front matter. Requiring a run, not just one
    clean chunk, matters: acknowledgments or a book-list page can read as
    genuine prose that no keyword catches, but they often sit right before a
    table of contents (which the numeric check does catch) -- so the run
    resets there and correctly pushes past both to the real content."""
    consecutive_clean = 0
    for i, chunk in enumerate(chunks):
        if looks_like_front_matter(chunk['chunk_text']):
            consecutive_clean = 0
        else:
            consecutive_clean += 1
            if consecutive_clean >= min_consecutive_clean:
                return i - min_consecutive_clean + 1
    return 0  # never found a clean run -- fall back to the original behavior