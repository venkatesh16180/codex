# test_db_connection.py -- Phase 20
#
# A fresh clone has no data/ directory, and get_connection() used to hand sqlite3 a path whose
# parent did not exist, which fails as 'unable to open database file' and says nothing about
# why. These tests point db.DB_PATH at a temp location (db.py imports DB_PATH by name, so it
# is db.DB_PATH that has to be patched, not config.DB_PATH) and never touch the real library.
import db


def test_get_connection_creates_a_missing_parent_directory(tmp_path, monkeypatch):
    target = tmp_path / 'not_there_yet' / 'nested' / 'librarian.db'
    monkeypatch.setattr(db, 'DB_PATH', str(target))
    assert not target.parent.exists()

    conn = db.get_connection()
    try:
        assert target.parent.is_dir()
        conn.execute('CREATE TABLE t (x)')   # a usable database, not just a folder
    finally:
        conn.close()


def test_get_connection_with_an_existing_directory_still_works(tmp_path, monkeypatch):
    target = tmp_path / 'librarian.db'          # parent (tmp_path) already exists
    monkeypatch.setattr(db, 'DB_PATH', str(target))

    db.get_connection().close()
    db.get_connection().close()                 # a second call must not trip on the directory


def test_get_connection_with_a_bare_filename_has_no_directory_to_create(tmp_path, monkeypatch):
    # os.path.dirname('librarian.db') is '' and os.makedirs('') raises, so this path needs a guard.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(db, 'DB_PATH', 'librarian.db')

    db.get_connection().close()
    assert (tmp_path / 'librarian.db').exists()
