"""Renders every page with Streamlit's AppTest. Hits live APIs, so it only runs with RUN_NETWORK_TESTS=1."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("RUN_NETWORK_TESTS"), reason="set RUN_NETWORK_TESTS=1 to render pages")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = sorted(f"views/{f}" for f in os.listdir(os.path.join(ROOT, "views")) if f.endswith(".py"))


@pytest.mark.parametrize("view", VIEWS)
def test_page_renders(view, database, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import auth
    monkeypatch.chdir(ROOT)
    auth.create_user("pagetest", "pagetest@example.com", "password-123")
    user = auth.verify_user("pagetest", "password-123")[0]
    at = AppTest.from_file("app.py", default_timeout=300)
    at.session_state["user"] = user
    if view != "views/home.py":
        at.switch_page(view)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
