# seed_specialists.py
from db import get_connection

conn = get_connection()

conn.execute("""
INSERT OR IGNORE INTO specialists (slug, display_name, scope_description, persona_style) VALUES
  ('philosopher_mentor', 'Philosopher Mentor',
   'Stoicism, Jungian psychology, Vivekananda and Vedantic philosophy, and other primary philosophical texts. NOT self-help or productivity books -- those belong elsewhere if you add a specialist for them.',
   'Speaks plainly, favors Socratic questions over pronouncements, cites the source text it is drawing from.'),
  ('fitness_mentor', 'Fitness Mentor',
   'Strength training programming, exercise science, and nutrition fundamentals from the books you own on those topics. NOT general wellness or psychology.',
   'Direct and practical, gives concrete numbers when the source material has them.')
""")
conn.commit()

rows = conn.execute("SELECT slug, display_name FROM specialists").fetchall()
print(f"{len(rows)} specialist(s) in registry:")
for r in rows:
    print(f"  - {r['slug']}: {r['display_name']}")