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
import pytest
from db import get_connection


@pytest.fixture(scope='session')
def conn():
    c = get_connection()
    yield c
    c.close()