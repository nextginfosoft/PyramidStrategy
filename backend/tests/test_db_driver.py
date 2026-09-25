"""
Guards the database driver contract.

Production uses plain ``postgresql://`` URLs and ships psycopg2-binary. SQLAlchemy 2.1
changed the default driver for that URL form to psycopg (v3), so an unpinned upgrade
made the app crash at import time (``No module named 'psycopg'``) — but only in the
Docker image, because every other test runs on SQLite. This test fails in CI the same
way if the installed SQLAlchemy ever defaults to a driver we don't ship.
"""

import pytest


def test_plain_postgres_url_resolves_to_the_driver_we_ship():
    pytest.importorskip("psycopg2")  # only meaningful where our declared driver is installed
    from sqlalchemy.engine import make_url

    dialect = make_url("postgresql://user:pw@db:5432/app").get_dialect()

    # import_dbapi() raises ModuleNotFoundError when SQLAlchemy defaults to a driver
    # that isn't installed — exactly the production crash this guards against.
    assert dialect.import_dbapi().__name__ == "psycopg2"
