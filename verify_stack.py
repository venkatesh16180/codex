import ollama, sqlite3
from sentence_transformers import SentenceTransformer

# 1. Ollama + tool-calling model responds at all
r = ollama.chat(model='qwen3:4b', messages=[{'role': 'user', 'content': 'Say OK.'}])
print('Ollama chat:', r.message.content[:50])

# 2. sentence-transformers loads and embeds
model = SentenceTransformer('all-MiniLM-L6-v2')
vec = model.encode('a test sentence')
print('Embedding shape:', vec.shape)   # expect (384,)

# 3. SQLite accepts the schema and enforces foreign keys
conn = sqlite3.connect('data/librarian.db')
conn.execute('PRAGMA foreign_keys = ON;')
conn.executescript(open('schema.sql').read())
print('Schema loaded OK')