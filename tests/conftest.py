"""
Test setup. Every test gets a throwaway SQLite database; nothing touches chainintel.db.

    pytest                         # unit tests (offline)
    pytest --postgres              # also run the database tests against a temporary Postgres (needs `pgserver`)
    RUN_NETWORK_TESTS=1 pytest     # also render every page against the live APIs
"""
import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.pop("DATABASE_URL", None)


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="also run database tests against Postgres (pgserver)")


def _reload_db_modules():
    import config, db, auth, notify, chainintel_core       # noqa: E401
    for mod in (config, db, chainintel_core, auth, notify):
        importlib.reload(mod)


@pytest.fixture(params=["sqlite", "postgres"])
def database(request, tmp_path, monkeypatch):
    """Fresh, migrated database for one test — SQLite always, Postgres when --postgres is given."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CHAININTEL_DB", str(tmp_path / "test.db"))
    if request.param == "postgres":
        if not request.config.getoption("--postgres"):
            pytest.skip("pass --postgres to run against Postgres")
        pgserver = pytest.importorskip("pgserver")
        server = pgserver.get_server(str(tmp_path / "pg"), cleanup_mode="stop")
        monkeypatch.setenv("DATABASE_URL", server.get_uri())
    _reload_db_modules()
    import auth, notify, chainintel_core                    # noqa: E401
    auth.init_user_db()
    notify.init_db()
    chainintel_core.RiskEngine.init_db(None)
    yield request.param
    monkeypatch.delenv("DATABASE_URL", raising=False)
