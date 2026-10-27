# download_models.py -- run ONCE on a new machine, with internet, before first use.
#
# Every Codex entry point sets HF_HUB_OFFLINE=1 so a running system never touches the
# network. The flip side is that on a fresh clone the embedding model is not cached yet,
# and offline mode forbids fetching it. This script does the one-time download (it
# deliberately does not set the offline flag), then reports which Ollama models are
# missing. It never pulls Ollama models itself -- those are multi-GB downloads you should
# start on purpose.
import os

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'   # keep in step with the SentenceTransformer(...) calls


def missing_ollama_models(required, installed):
    """Names in `required` that are not in `installed`. A bare name like 'llama3.2'
    matches the 'llama3.2:latest' that Ollama reports for it."""
    have = set(installed)
    return [name for name in required if name not in have and f'{name}:latest' not in have]


def main():
    os.environ.pop('HF_HUB_OFFLINE', None)   # in case the shell exported it
    from sentence_transformers import SentenceTransformer
    from config import CHAT_MODEL, LIBRARIAN_MODEL

    print(f'Downloading the embedding model {EMBEDDING_MODEL} (cached after the first run)...')
    SentenceTransformer(EMBEDDING_MODEL)
    print('Embedding model ready.')

    import ollama
    try:
        installed = [getattr(m, 'model', None) or m.get('name') for m in ollama.list().models]
    except Exception as e:
        print(f'Could not reach Ollama ({type(e).__name__}); start it, then rerun this to check the models.')
        return
    missing = missing_ollama_models(sorted({LIBRARIAN_MODEL, CHAT_MODEL}), installed)
    if missing:
        print('Missing Ollama models -- run these yourself:')
        for name in missing:
            print(f'  ollama pull {name}')
    else:
        print('Ollama models present.')


if __name__ == '__main__':
    main()
