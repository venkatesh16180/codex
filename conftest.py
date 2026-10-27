# conftest.py -- Phase 15
#
# Deliberately NOT an isolated in-memory schema.sql fixture: this project's
# existing test convention (test_isolation.py) runs against the real,
# production database via db.get_connection(), with tests that insert their
# own throwaway rows and delete them in a finally block. This file follows
# the same philosophy for the new pytest-based tests, rather than inventing
# a second, disconnected testing convention.
#
# pytest is a new dependency as of Phase 15 -- add it to requirements.in
# and reinstall/recompile before running this.
import os
import sqlite3
import tempfile

# Phase 20: keep test runs out of the real data/codex.log. Before this, tests wrote lines
# (e.g. an export count for a temp path) into the production log, where they had to be told
# apart from real runs. This must run before anything imports config.py / logging_setup.py.
os.environ.setdefault('CODEX_LOG_PATH', os.path.join(tempfile.gettempdir(), 'codex-tests.log'))

import pytest
from db import get_connection


@pytest.fixture(scope='session')
def conn():
    c = get_connection()
    yield c
    c.close()


@pytest.fixture
def fresh_db():
    """An isolated in-memory database built from the real schema.sql, one per test.
    Added in Phase 20 alongside (not instead of) the live-database `conn` fixture above:
    tests that insert into pending_actions, or that must prove schema.sql itself
    builds, must not touch the real library."""
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    with open('schema.sql', encoding='utf-8') as f:
        c.executescript(f.read())
    yield c
    c.close()
