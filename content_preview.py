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


# Phase 20: moved here from agent.py so the Librarian's preview and the classifier
# share one definition (classifier_triage.py used to import all of agent.py -- and
# build an Ollama client at import time -- just to read this constant).
FRONT_MATTER_SCAN_LIMIT = 30  # generous headroom past Rich Dad Poor Dad's real
                              # example (front matter ended at chunk 7)

# Text length the classifier sees. Training (export_triage_labels.py) and serving
# (classifier_triage.py) both go through build_classifier_text(), so this value is
# part of the model's contract: changing it means re-export + retrain. The saved
# model records it, and classifier_triage warns on a mismatch.
CLASSIFIER_MAX_CHARS = 16000  # chosen by Phase 11's sweep on a 22-document corpus


def build_classifier_text(chunks: list, max_chars: int = CLASSIFIER_MAX_CHARS) -> tuple:
    """The ONE place classifier input text is built, for training and for serving.

    Skips front matter (same logic as the Librarian's preview), joins chunk text
    with spaces, and caps at max_chars. Returns (text, truncated).

    Why this exists: before Phase 20 the export joined chunks from index 0 with
    blank lines and front matter included, while serving skipped front matter,
    joined with spaces and sliced -- so the model was scored on text it was never
    trained on. `chunks` are rows or dicts with a 'chunk_text' key, in order."""
    start = find_real_content_start(chunks[:FRONT_MATTER_SCAN_LIMIT])
    parts, total, truncated = [], 0, False
    for chunk in chunks[start:]:
        if total >= max_chars:
            truncated = True
            break
        parts.append(chunk['chunk_text'])
        total += len(chunk['chunk_text']) + 1
    text = ' '.join(parts)
    if len(text) > max_chars:
        text, truncated = text[:max_chars], True
    return text, truncated
