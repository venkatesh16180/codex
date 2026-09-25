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

# Phase 14
LLM_TRIAGE_TIMEOUT_SEC = _get_int('CODEX_LLM_TRIAGE_TIMEOUT_SEC', 10800)
# 3hr ceiling -- margin above the real 124.6-min max triage run (Phase 13
# async stress test).
LLM_CHAT_TIMEOUT_SEC = _get_int('CODEX_LLM_CHAT_TIMEOUT_SEC', 420)
# was 90 -- real testing (Phase 16) showed a cold model load on this
# hardware taking over 180s for llama3.2 (ollama run's CLI doesn't print an
# exact figure, so this is real margin above an observed lower bound, not a
# precisely measured one). Still user-facing and still meant to fail
# eventually, not hang forever -- OLLAMA_KEEP_ALIVE=30m (set at the OS
# level, Phase 16) is the real fix for repeated cold starts; this timeout
# is the safety net for the unavoidable first one after an Ollama/machine
# restart.
MAX_CHARS_WARNING = _get_int('CODEX_MAX_CHARS_WARNING', 500_000)
# logged warning only, not a hard reject -- doc 22 (2.87M chars) was a
# real document, not a bug.
LLM_CONNECT_TIMEOUT_SEC = _get_int('CODEX_LLM_CONNECT_TIMEOUT_SEC', 10)
# separate from the read timeouts above -- a plain float passed to
# ollama.Client(timeout=...) sets connect/read/write/pool timeouts ALL to
# that value. Without this, a down Ollama server would hang for up to 3hr
# just trying to connect, before the retry wrapper ever saw a ConnectError.