# logging_setup.py
import logging
import logging.handlers
from config import LOG_LEVEL, LOG_PATH
 
_configured = False
 
def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        root = logging.getLogger()
        root.setLevel(LOG_LEVEL)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)-8s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)
 
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=2_000_000, backupCount=3
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
 
        _configured = True

        # Third-party libraries inherit root's INFO level and handlers too --
        # without this, every Ollama HTTP call (httpx) and every embedding
        # model load (sentence_transformers) floods codex.log alongside your
        # own agent/review_pending entries.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('sentence_transformers').setLevel(logging.WARNING)

    return logging.getLogger(name)
