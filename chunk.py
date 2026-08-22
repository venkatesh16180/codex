def chunk_text(text: str, target_words: int = 180, overlap_words: int = 30) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + target_words
        chunks.append(' '.join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap_words
    return chunks