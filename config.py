# config.py
import os
from dotenv import load_dotenv
 
load_dotenv()  # must run before any _get_* call below
 
def _get_str(key, default):
    return os.environ.get(key, default)
 
def _get_int(key, default):
    return int(os.environ.get(key, default))
 
def _get_float(key, default):
    return float(os.environ.get(key, default))
 
DB_PATH = _get_str('CODEX_DB_PATH', 'data/librarian.db')
LIBRARIAN_MODEL = _get_str('CODEX_LIBRARIAN_MODEL', 'qwen3:4b')
CHAT_MODEL = _get_str('CODEX_CHAT_MODEL', 'llama3.2')
HISTORY_TURNS = _get_int('CODEX_HISTORY_TURNS', 3)
RELEVANCE_THRESHOLD = _get_float('CODEX_RELEVANCE_THRESHOLD', 0.3)
NUM_CTX = _get_int('CODEX_NUM_CTX', 8192)
LOG_LEVEL = _get_str('CODEX_LOG_LEVEL', 'INFO')
LOG_PATH = _get_str('CODEX_LOG_PATH', 'data/codex.log')
